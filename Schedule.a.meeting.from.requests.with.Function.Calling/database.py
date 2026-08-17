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
from sqlalchemy import String, Text, DateTime, JSON, Index
from sqlalchemy.types import TypeDecorator, Text
from utilities.security import encrypt_envelope, decrypt_envelope



DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/calendar_service",
)


class EncryptedString(TypeDecorator):
    """Transparently encrypts strings on save and decrypts on load."""
    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is not None:
            return encrypt_envelope(value)
        return value

    def process_result_value(self, value, dialect):
        if value is not None:
            return decrypt_envelope(value)
        return value


class Base(DeclarativeBase):
    pass


class UserDB(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)

    google_sub: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
    )

    email: Mapped[str] = mapped_column(
        String(320),
        unique=True,
        index=True,
    )

    name: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )

    picture: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )


class OAuthTokenDB(Base):
    __tablename__ = "oauth_tokens"

    id: Mapped[int] = mapped_column(primary_key=True)

    user_id: Mapped[int] = mapped_column(
        index=True,
    )

    access_token: Mapped[str] = mapped_column(
        EncryptedString,
    )

    refresh_token: Mapped[Optional[str]] = mapped_column(
        EncryptedString,
        nullable=True,
    )

    token_uri: Mapped[str] = mapped_column(
        String(500),
        default="https://oauth2.googleapis.com/token",
    )

    client_id: Mapped[str] = mapped_column(
        EncryptedString,
    )

    client_secret: Mapped[str] = mapped_column(
        EncryptedString,
    )

    scopes: Mapped[list] = mapped_column(
        JSON,
    )

    expiry: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    __table_args__ = (
        Index(
            "ix_oauth_user_id",
            "user_id",
            unique=True,
        ),
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

    request_text: Mapped[str] = mapped_column(
        Text,
    )

    summary: Mapped[str] = mapped_column(
        String(255),
    )

    start_time: Mapped[str] = mapped_column(
        String(100),
    )

    end_time: Mapped[str] = mapped_column(
        String(100),
    )

    attendees: Mapped[list] = mapped_column(
        JSON,
        default=list,
    )

    meeting_link: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    google_event_id: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
    )

    status: Mapped[str] = mapped_column(
        String(50),
        default="scheduled",
    )

    raw_function_call: Mapped[dict] = mapped_column(
        JSON,
        default=dict,
    )

    error_message: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
    )


engine: AsyncEngine = create_async_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    pool_recycle=1800,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    await engine.dispose()


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session