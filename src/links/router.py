import re
from datetime import datetime
import string
import secrets

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, insert, update, delete

from database import get_async_session
from auth.users import current_user, current_active_user
from auth.db import User
from links.models import links as Link
from links.schemas import LinkCreate, LinkRead, LinkUpdate


router = APIRouter(prefix="/links", tags=["links"])

RESERVED_CODES = {"docs", "redoc", "openapi", "auth", "links"}


def generate_random_code(length: int = 6) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


@router.post("/shorten", response_model=LinkRead, status_code=status.HTTP_201_CREATED)
async def create_short_link(
    data: LinkCreate,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_user),
):
    """
    Create a new short link. If authenticated, the link will be associated with the user.
    Supports optional custom alias and expiration date.
    """
    alias = data.alias
    if alias:
        alias = alias.strip()
        if not re.match("^[A-Za-z0-9_-]+$", alias):
            raise HTTPException(
                status_code=400,
                detail="Alias may only contain letters, digits, '_' or '-'.",
            )
        if alias.lower() in RESERVED_CODES:
            raise HTTPException(
                status_code=400, detail="This alias is reserved or not allowed."
            )

        statement = select(Link).filter(Link.c.short_code == alias)
        result = await session.execute(statement)
        existing = result.scalar_one_or_none()
        if existing:
            raise HTTPException(
                status_code=400, detail="Alias already in use. Please choose another."
            )
        short_code = alias
    else:
        short_code = None
        while True:
            code_candidate = generate_random_code(6)
            if code_candidate.lower() in RESERVED_CODES:
                continue
            statement = select(Link).filter(Link.c.short_code == code_candidate)
            result = await session.execute(statement)
            if not result.scalar_one_or_none():
                short_code = code_candidate
                break

    owner_id = None
    if user is not None:
        owner_id = getattr(user, "id", None)

    # Create Link record
    new_link = {
        "user_id": owner_id,
        "original_url": str(data.original_url),
        "short_code": short_code,
        "created_at": datetime.now(),
        "expires_at": data.expires_at.replace(tzinfo=None),
        "click_count": 0
    }
    statement = insert(Link).values(**new_link)
    await session.execute(statement)
    await session.commit()
    return new_link


@router.get("/search", response_model=list[LinkRead])
async def search_links(
    original_url: str = Query(..., description="Original URL to search for"),
    session: AsyncSession = Depends(get_async_session),
    user=Depends(current_active_user),
):
    """
    Search for shortened links by original URL. Returns links owned by the current user that match the URL.
    """
    # Ensure user is authenticated (current_active_user dependency does this)
    statement = select(Link).filter(
        Link.c.user_id == user.id, Link.c.original_url == original_url
    )
    result = await session.execute(statement)
    links = result.all()
    return links


@router.get("/{short_code}")
async def redirect_to_url(
    short_code: str, 
    session: AsyncSession = Depends(get_async_session),
    user=Depends(current_user),
):
    """
    Redirect to the original URL corresponding to the given short code.
    Increments the click counter. Returns 404 if not found or expired.
    """
    statement = select(Link).where(Link.c.short_code == short_code)
    result = await session.execute(statement)
    link = result.all()
    if link is None or len(link) == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Link not found"
        )
    link = link[0]
    user_id = getattr(user, "id", None)

    if link.user_id and (user_id is None or link.user_id != user_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed"
        )

    if link.expires_at and datetime.utcnow() > link.expires_at:
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="Link has expired")

    statement = update(Link).where(Link.c.short_code == short_code).values(click_count=Link.c.click_count + 1)
    await session.execute(statement)
    await session.commit()
    return RedirectResponse(url=link.original_url)


@router.get("/{short_code}/stats", response_model=LinkRead)
async def get_link_stats(
    short_code: str,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(current_active_user),
):
    """
    Get statistics for a short link (only available to the owner).
    """
    statement = select(Link).filter(Link.c.short_code == short_code)
    result = await session.execute(statement)
    link = result.all()
    if link is None or len(link) == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Link not found"
        )
    link = link[0]
    if link.user_id is None or link.user_id != user.id:
        # If the link has no owner (anonymous) or belongs to someone else, forbid access
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed to view stats"
        )
    return link


@router.put("/{short_code}", response_model=LinkRead)
async def update_link(
    short_code: str,
    data: LinkUpdate,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(current_active_user),
):
    """
    Update an existing short link's original URL or expiration date (owner only).
    """
    statement = select(Link).filter(Link.c.short_code == short_code)
    result = await session.execute(statement)
    link = result.all()
    if link is None or len(link) == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Link not found"
        )
    link = link[0]
    if link.user_id is None or link.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not allowed to update this link",
        )

    statement = update(Link).where(Link.c.short_code == short_code).values(original_url=str(data.original_url))
    await session.execute(statement)
    await session.commit()

    statement = select(Link).filter(Link.c.short_code == short_code)
    result = await session.execute(statement)
    link = result.all()[0]

    return link


@router.delete("/{short_code}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_link(
    short_code: str,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(current_active_user),
):
    """
    Delete a short link. Only the owner can delete. Anonymous links cannot be deleted via API (no owner).
    """
    statement = select(Link).filter(Link.c.short_code == short_code)
    result = await session.execute(statement)
    link = result.all()
    if link is None or len(link) == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Link not found"
        )
    link = link[0]
    if link.user_id is None or link.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not allowed to delete this link",
        )
    

    statement = delete(Link).filter(Link.c.short_code == short_code)
    await session.execute(statement)
    await session.commit()
    return {"detail": "Link deleted successfully"}
