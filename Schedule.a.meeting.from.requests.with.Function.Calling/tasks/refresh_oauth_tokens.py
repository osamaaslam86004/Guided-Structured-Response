import asyncio
import logging
from datetime import datetime, timedelta

from celery_app import celery_app
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import NullPool

from config.settings import settings
from models.auth_db import OAuthTokenDB
from utilities.cache import set_cached_function_call

logger = logging.getLogger(__name__)


ASYNC_DB_URL = str(settings.db.async_url)


def get_task_sessionmaker() -> tuple[object, async_sessionmaker[AsyncSession]]:
    _worker_engine = create_async_engine(ASYNC_DB_URL, poolclass=NullPool)
    _worker_sessionmaker = async_sessionmaker(
        _worker_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    return _worker_engine, _worker_sessionmaker


async def _rotate_tokens(threshold_minutes: int = 10) -> int:
    """Refresh OAuth tokens that are expired or expiring within threshold_minutes.

    Returns number of tokens refreshed.
    """

    now = datetime.utcnow()
    threshold = now + timedelta(minutes=threshold_minutes)

    _worker_engine, _worker_sessionmaker = get_task_sessionmaker()
    refreshed_count = 0

    try:
        async with _worker_sessionmaker() as session:
            stmt = select(OAuthTokenDB).where(
                OAuthTokenDB.refresh_token.isnot(None),
                (OAuthTokenDB.expiry.is_(None)) | (OAuthTokenDB.expiry <= threshold),
            )

            result = await session.execute(stmt)
            tokens = result.scalars().all()

            for token in tokens:
                try:
                    # Build transient credentials with refresh token
                    credentials = Credentials(
                        token=token.access_token,
                        refresh_token=token.refresh_token,
                        token_uri=token.token_uri,
                        client_id=token.client_id,
                        client_secret=token.client_secret,
                        scopes=token.scopes,
                        expiry=token.expiry,
                    )

                    # Refresh may block; run in threadpool to avoid blocking loop
                    await asyncio.to_thread(lambda: credentials.refresh(Request()))

                    token.access_token = credentials.token
                    token.expiry = credentials.expiry

                    # Update Redis cache for this user
                    cache_key = f"google_oauth_token:{token.user_id}"
                    cache_payload = {
                        "access_token": credentials.token,
                        "refresh_token": credentials.refresh_token,
                        "token_uri": credentials.token_uri,
                        "client_id": credentials.client_id,
                        "client_secret": credentials.client_secret,
                        "scopes": credentials.scopes,
                        "expiry": (
                            credentials.expiry.isoformat()
                            if credentials.expiry
                            else None
                        ),
                    }

                    await set_cached_function_call(
                        cache_key=cache_key, data=cache_payload, expire_seconds=3600
                    )

                    refreshed_count += 1
                except Exception as exc:
                    logger.exception(
                        "Failed to refresh token for user %s: %s", token.user_id, exc
                    )

            # Commit any updated token rows
            await session.commit()

    finally:
        await _worker_engine.dispose()

    return refreshed_count


@celery_app.task(name="tasks.rotate_oauth_tokens")
def rotate_oauth_tokens():
    """Celery task wrapper that runs the async rotation routine.

    This task is intended to be scheduled periodically (beat).
    """
    try:
        refreshed = asyncio.run(_rotate_tokens(threshold_minutes=10))
        logger.info("Rotated %d OAuth tokens", refreshed)
        return {"refreshed": refreshed}
    except Exception as exc:
        logger.exception("OAuth rotation failed: %s", exc)
        raise
