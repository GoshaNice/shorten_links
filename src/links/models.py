from sqlalchemy import Table, Column, Integer, DateTime, MetaData, String
from sqlalchemy.dialects.postgresql import UUID

metadata = MetaData()

links = Table(
    "links",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("user_id", UUID, nullable=True),
    Column("original_url", String(length=2048), nullable=False),
    Column("short_code", String(length=100), nullable=False, unique=True, index=True),
    Column("created_at", DateTime, nullable=False),
    Column("expires_at", DateTime, nullable=True),
    Column("click_count", Integer, nullable=False, default=0),
)
