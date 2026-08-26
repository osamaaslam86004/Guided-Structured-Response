# database.py
# This moves the service from file-based SQLite to PostgreSQL using SQLAlchemy's
# async engine and asyncpg

import os
from datetime import datetime
from typing import Optional

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, Text, DateTime, JSON, Float, Integer, Boolean, Index
from sqlalchemy.types import TypeDecorator, Text
from models.base import Base
from utilities.security import encrypt_envelope, decrypt_envelope

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/calendar_service",
)


class CalendarEventDB(Base):
    __tablename__ = "calendar_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        index=True,
    )
    task_id: Mapped[Optional[str]] = mapped_column(
        String(255),
        index=True,
        nullable=True,
    )
    request_text: Mapped[str] = mapped_column(Text)
    summary: Mapped[str] = mapped_column(String(255))
    start_time: Mapped[str] = mapped_column(String(100))
    end_time: Mapped[str] = mapped_column(String(100))
    attendees: Mapped[list] = mapped_column(JSON, default=list)
    meeting_link: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    google_event_id: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="scheduled")
    raw_function_call: Mapped[dict] = mapped_column(JSON, default=dict)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
    )
