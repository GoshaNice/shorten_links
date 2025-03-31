from fastapi import FastAPI, Depends
from fastapi_cache.backends.redis import RedisBackend
from fastapi_cache import FastAPICache
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from auth.schemas import UserCreate, UserRead
from redis import asyncio as aioredis

from auth.users import auth_backend, current_active_user, fastapi_users
from auth.db import User
from links.router import router as links_router
from config import REDIS_HOST

import uvicorn


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    redis = aioredis.from_url(f"redis://{REDIS_HOST}")
    FastAPICache.init(RedisBackend(redis), prefix="fastapi-cache")
    yield


app = FastAPI(lifespan=lifespan)

app.include_router(
    fastapi_users.get_auth_router(auth_backend), prefix="/auth/jwt", tags=["auth"]
)
# Include authentication and user management routes
app.include_router(
    fastapi_users.get_register_router(UserRead, UserCreate),
    prefix="/auth",
    tags=["auth"],
)
# Include link management routes under /links
app.include_router(links_router)


@app.get("/protected-route")
def protected_route(user: User = Depends(current_active_user)):
    return f"Hello, {user.email}"


@app.get("/unprotected-route")
def unprotected_route():
    return "Hello, anonym"


if __name__ == "__main__":
    uvicorn.run("main:app", reload=True, host="0.0.0.0", log_level="info")
