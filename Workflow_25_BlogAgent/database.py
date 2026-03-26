# database.py
# PostgreSQL models & connection using SQLAlchemy (async)

from __future__ import annotations

import os
from datetime import datetime
from enum import Enum as PyEnum
from typing import Optional

from dotenv import load_dotenv, find_dotenv
from sqlalchemy import (
    Column, String, Text, DateTime, Enum,
    Integer, func,
)
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from typing import AsyncGenerator

load_dotenv(find_dotenv())

# ──────────────────────────────────────────────────────────────
# Connection
# ──────────────────────────────────────────────────────────────

PG_USER     = os.getenv("PG_USER",     "blogger")
PG_PASSWORD = os.getenv("PG_PASSWORD", "abcd1234")
PG_HOST     = os.getenv("PG_HOST",     "localhost")
PG_PORT     = os.getenv("PG_PORT",     "5432")
PG_DB       = os.getenv("PG_DB",       "blogs")

DATABASE_URL = (
    f"postgresql+asyncpg://{PG_USER}:{PG_PASSWORD}"
    f"@{PG_HOST}:{PG_PORT}/{PG_DB}"
)

engine = create_async_engine(DATABASE_URL, echo=False, future=True)

AsyncSessionLocal = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


# ──────────────────────────────────────────────────────────────
# Base
# ──────────────────────────────────────────────────────────────

class Base(DeclarativeBase):
    pass


# ──────────────────────────────────────────────────────────────
# Enums
# ──────────────────────────────────────────────────────────────

class BlogStatus(str, PyEnum):
    PENDING   = "PENDING"    # workflow paused — waiting for human review
    APPROVED  = "APPROVED"   # human approved — workflow finalising
    REJECTED  = "REJECTED"   # human rejected — workflow handled rejection
    COMPLETED = "COMPLETED"  # workflow finished successfully
    FAILED    = "FAILED"     # workflow encountered unrecoverable error


# ──────────────────────────────────────────────────────────────
# Model
# ──────────────────────────────────────────────────────────────

class BlogPost(Base):
    __tablename__ = "blog_posts"

    # Primary key — auto-increment integer
    id = Column(Integer, primary_key=True, autoincrement=True)

    # LangGraph checkpoint thread — links Postgres row ↔ SQLite checkpoint
    thread_id = Column(String(128), unique=True, nullable=False, index=True)

    # User-supplied topic
    topic = Column(Text, nullable=False)

    # Generated blog title (populated after orchestrator runs)
    blog_title = Column(Text, nullable=True)

    # Full markdown content (populated after workflow reaches HITL checkpoint)
    content = Column(Text, nullable=True)

    # Workflow status
    status = Column(
        Enum(BlogStatus, name="blogstatus"),
        nullable=False,
        default=BlogStatus.PENDING,
        server_default=BlogStatus.PENDING.value,
    )

    # Human review fields
    rejection_reason = Column(Text, nullable=True)

    # Timestamps
    created_at  = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at  = Column(DateTime(timezone=True), server_default=func.now(),
                         onupdate=func.now(), nullable=False)
    approved_at = Column(DateTime(timezone=True), nullable=True)
    rejected_at = Column(DateTime(timezone=True), nullable=True)

    def to_dict(self) -> dict:
        return {
            "id":               self.id,
            "thread_id":        self.thread_id,
            "topic":            self.topic,
            "blog_title":       self.blog_title,
            "content":          self.content,
            "status":           self.status.value if self.status else None,
            "rejection_reason": self.rejection_reason,
            "created_at":       self.created_at.isoformat()  if self.created_at  else None,
            "updated_at":       self.updated_at.isoformat()  if self.updated_at  else None,
            "approved_at":      self.approved_at.isoformat() if self.approved_at else None,
            "rejected_at":      self.rejected_at.isoformat() if self.rejected_at else None,
        }


# ──────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency — yields an async DB session."""
    async with AsyncSessionLocal() as session:
        yield session


async def init_db() -> None:
    """Create all tables if they don't exist (run once at startup)."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


