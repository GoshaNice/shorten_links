from datetime import datetime
from typing import Optional
from pydantic import BaseModel, HttpUrl


class LinkBase(BaseModel):
    original_url: HttpUrl
    expires_at: Optional[datetime] = None


class LinkCreate(LinkBase):
    """Schema for creating a new short link."""

    alias: Optional[str] = None  # custom short code (optional)


class LinkUpdate(BaseModel):
    """Schema for updating an existing short link."""

    original_url: HttpUrl


class LinkRead(BaseModel):
    """Schema for reading link info (including stats)."""

    short_code: str
    original_url: HttpUrl
    created_at: datetime
    expires_at: Optional[datetime] = None
    click_count: int

    class Config:
        orm_mode = True
