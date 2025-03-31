from datetime import datetime
from typing import Optional
from pydantic import BaseModel, HttpUrl


class LinkBase(BaseModel):
    original_url: HttpUrl
    expires_at: Optional[datetime] = None


class LinkCreate(LinkBase):
    alias: Optional[str] = None


class LinkUpdate(BaseModel):
    original_url: HttpUrl


class LinkRead(BaseModel):
    short_code: str
    original_url: HttpUrl
    created_at: datetime
    expires_at: Optional[datetime] = None
    click_count: int

    class Config:
        orm_mode = True
