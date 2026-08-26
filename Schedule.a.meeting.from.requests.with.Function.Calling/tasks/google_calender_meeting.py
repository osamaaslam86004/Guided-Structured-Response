# tasks.py

import asyncio
from config.settings import settings

from celery.exceptions import MaxRetriesExceededError
from googleapiclient.errors import HttpError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from celery_app import celery_app
from models.google_calender_db import CalendarEventDB
from engine import get_calendar_engine
from tasks.events import publish_task_event
from services.google_calender import service
from dlq import push_dead_letter

TRANSIENT_HTTP_CODES = {429, 500, 502, 503, 504}

# 1. Reuse central settings to resolve database URL and async driver
ASYNC_DB_URL = str(settings.db.sync_url)

# Worker-level engine instance (Reused across task runs within the same worker process)
_worker_engine: AsyncEngine | None = None
_worker_sessionmaker: async_sessionmaker[AsyncSession] | None = None


def get_task_sessionmaker() -> async_sessionmaker[AsyncSession]:
    """
    Lazily instantiates and caches the AsyncEngine for the Celery process.
    Eliminates engine creation overhead on every task run.

    Since Celery worker processes execute multiple tasks over their lifecycle,
    creating a module-level or worker-scoped engine backed by asyncpg avoids
    re-authenticating and rebuilding the connection engine on every run

    Connection Pooling: Instead of creating and disposing an engine per task (poolclass=NullPool),
    the module caches _worker_engine using standard connection pooling parameters
    (pool_size, max_overflow).
    """
    global _worker_engine, _worker_sessionmaker
    if _worker_engine is None:
        _worker_engine = create_async_engine(
            ASYNC_DB_URL,
            pool_pre_ping=True,
            pool_size=settings.db.pool_size,
            max_overflow=settings.db.max_overflow,
            pool_recycle=1800,
        )
        _worker_sessionmaker = async_sessionmaker(
            _worker_engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _worker_sessionmaker


async def _execute_schedule(
    task_id: str,
    user_id: int,
    request_text: str,
):
    """
    Execute the calendar scheduling task using the cached worker sessionmaker

    Prevents Event Loop Contamination: Calling asyncio.run() creates a clean event
    loop per task execution. Because pool_pre_ping=True is enabled, connections drawn
    from the pool inside asyncio.run() validate automatically without event loop attachment
    conflicts (It means, the database session's async loop remain bind to this celery task event
    loop to prevent error:
    `attached to a different loop`).
    """

    TaskAsyncSession = get_task_sessionmaker()

    publish_task_event(
        task_id,
        {"type": "TASK_STARTED", "task_id": task_id},
    )

    engine_instance = get_calendar_engine()

    publish_task_event(
        task_id,
        {"type": "LLM_STARTED", "task_id": task_id},
    )

    func_call = engine_instance.extract_calendar_function(request_text)

    publish_task_event(
        task_id,
        {"type": "LLM_COMPLETED", "task_id": task_id},
    )

    publish_task_event(
        task_id,
        {"type": "GOOGLE_CALENDAR_STARTED", "task_id": task_id},
    )

    # Persist record using task-scoped async session from pooled engine
    async with TaskAsyncSession() as session:

        # Ensure gcal_service uses the task-scoped DB session
        gcal_service = await get_gcal_service(user_id=user_id, session=session)

        gcal_response = await gcal_service.create_event_with_meet(func_call)
        meeting_link = gcal_response.get("meeting_link")

        record = CalendarEventDB(
            user_id=user_id,
            task_id=task_id,
            request_text=request_text,
            summary=func_call.summary,
            start_time=func_call.start.date_time,
            end_time=func_call.end.date_time,
            attendees=[str(email) for email in func_call.attendees],
            meeting_link=meeting_link,
            google_event_id=gcal_response.get("event_id"),
            status=gcal_response.get("status", "scheduled"),
            raw_function_call=func_call.model_dump(),
        )
        session.add(record)
        await session.commit()

    result = {
        "function_call": func_call.model_dump(),
        "google_calendar_event": gcal_response,
        "meeting_link": meeting_link,
    }

    publish_task_event(
        task_id,
        {
            "type": "TASK_COMPLETED",
            "task_id": task_id,
            "result": result,
        },
    )

    return result


@celery_app.task(
    bind=True,
    name="tasks.execute_calendar_schedule_task",
    soft_time_limit=1200,
    time_limit=1500,
    max_retries=5,
    acks_late=True,
)
def execute_calendar_schedule_task(
    self,
    user_id: int,
    request_text: str,
):
    """
    This is deliberately not:
    autoretry_for=(Exception,)

    Automatically retrying every exception is a bad production strategy because malformed model output,
    invalid OAuth credentials, invalid attendee addresses, programming errors, and other permanent
    failures don't become transient merely because Celery is feeling optimistic.
    Now failed jobs don't simply disappear into the Celery abyss.
    """
    task_id = self.request.id

    try:
        return asyncio.run(
            _execute_schedule(
                task_id=task_id,
                user_id=user_id,
                request_text=request_text,
            )
        )
    except HttpError as exc:
        status = getattr(exc.resp, "status", None)
        if status not in TRANSIENT_HTTP_CODES:
            raise

        try:
            raise self.retry(
                exc=exc,
                countdown=(2**self.request.retries),
            )
        except MaxRetriesExceededError:
            publish_task_event(
                task_id,
                {
                    "type": "TASK_DEAD_LETTER",
                    "task_id": task_id,
                    "error": str(exc),
                },
            )
            raise

    except TimeoutError as exc:
        try:
            raise self.retry(
                exc=exc,
                countdown=(2**self.request.retries),
            )
        except MaxRetriesExceededError:
            push_dead_letter(
                task_id=task_id,
                user_id=user_id,
                request_text=request_text,
                error=str(exc),
            )
            raise
