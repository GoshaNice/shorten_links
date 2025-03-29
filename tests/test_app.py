import pytest
from httpx import AsyncClient
from fastapi import status
from main import app
from core.database import Base, engine

@pytest.fixture(autouse=True, scope="module")
async def setup_database():
    # Create database tables for testing
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    # Drop tables after tests
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest.mark.asyncio
async def test_anonymous_link_creation_and_redirect():
    async with AsyncClient(app=app, base_url="http://testserver") as client:
        # Create a short link without authentication
        response = await client.post("/links/shorten", json={"original_url": "http://example.com"})
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert "short_code" in data
        short_code = data["short_code"]
        # Check redirect
        resp = await client.get(f"/{short_code}", allow_redirects=False)
        # Expect a redirect status (307 Temporary Redirect)
        assert resp.status_code in (status.HTTP_302_FOUND, status.HTTP_307_TEMPORARY_REDIRECT)
        # The 'Location' header should be the original URL
        assert resp.headers.get("location") == "http://example.com"
        # Stats endpoint should be unauthorized for anonymous (no token)
        stats_resp = await client.get(f"/links/{short_code}/stats")
        assert stats_resp.status_code == status.HTTP_401_UNAUTHORIZED

@pytest.mark.asyncio
async def test_authenticated_link_management():
    async with AsyncClient(app=app, base_url="http://testserver") as client:
        # Register a new user
        reg_resp = await client.post("/auth/register", json={
            "email": "user@example.com",
            "password": "Secret123"
        })
        assert reg_resp.status_code == status.HTTP_201_CREATED
        # Login to get token
        login_resp = await client.post("/auth/jwt/login", data={
            "username": "user@example.com",
            "password": "Secret123"
        })
        assert login_resp.status_code == status.HTTP_200_OK
        token = login_resp.json().get("access_token")
        headers = {"Authorization": f"Bearer {token}"}
        # Create a link as authenticated user
        create_resp = await client.post("/links/shorten", json={
            "original_url": "https://fastapi.tiangolo.com",
            "alias": "fastapi-docs"
        }, headers=headers)
        assert create_resp.status_code == status.HTTP_201_CREATED
        link_data = create_resp.json()
        assert link_data["short_code"] == "fastapi-docs"
        # Get stats for the new link (initially click_count = 0)
        stats_resp = await client.get(f"/links/{link_data['short_code']}/stats", headers=headers)
        assert stats_resp.status_code == status.HTTP_200_OK
        stats = stats_resp.json()
        assert stats["click_count"] == 0
        # Access the link to increment click count
        _ = await client.get(f"/{link_data['short_code']}", allow_redirects=False)
        stats_resp2 = await client.get(f"/links/{link_data['short_code']}/stats", headers=headers)
        assert stats_resp2.json()["click_count"] == 1
        # Update the link's original URL
        new_url = "https://www.example.com"
        update_resp = await client.put(f"/links/{link_data['short_code']}", json={
            "original_url": new_url
        }, headers=headers)
        assert update_resp.status_code == status.HTTP_200_OK
        # Try to delete the link
        del_resp = await client.delete(f"/links/{link_data['short_code']}", headers=headers)
        assert del_resp.status_code == status.HTTP_204_NO_CONTENT
        # Ensure it is actually deleted (redirect now returns 404)
        resp404 = await client.get(f"/{link_data['short_code']}", allow_redirects=False)
        assert resp404.status_code == status.HTTP_404_NOT_FOUND
