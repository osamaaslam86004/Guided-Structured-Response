# tasks.py

# This is deliberately not:
# autoretry_for=(Exception,)

# Automatically retrying every exception is a bad production strategy because malformed model output,
#  invalid OAuth credentials, invalid attendee addresses, programming errors, and other permanent
# failures don't become transient merely because Celery is feeling optimistic.
# Now failed jobs don't simply disappear into the Celery abyss.


import asyncio

from celery.exceptions import MaxRetriesExceededError
from googleapiclient.errors import HttpError

from celery_app import celery_app
from database import (
    AsyncSessionLocal,
    CalendarEventDB,
)
from engine import get_calendar_engine
from events import publish_task_event
from gcloud_service import get_gcal_service
from dlq import push_dead_letter

TRANSIENT_HTTP_CODES = {
    429,
    500,
    502,
    503,
    504,
}


async def _execute_schedule(
    task_id: str,
    user_id: int,
    request_text: str,
):
    publish_task_event(
        task_id,
        {
            "type": "TASK_STARTED",
            "task_id": task_id,
        },
    )

    engine_instance = get_calendar_engine()

    publish_task_event(
        task_id,
        {
            "type": "LLM_STARTED",
            "task_id": task_id,
        },
    )

    # Extract function call structure via Outlines
    func_call = engine_instance.extract_calendar_function(request_text)

    publish_task_event(
        task_id,
        {
            "type": "LLM_COMPLETED",
            "task_id": task_id,
        },
    )

    # Call Google Calendar API to create event and generate Google Meet Link
    gcal_service = await get_gcal_service(user_id=user_id)

    publish_task_event(
        task_id,
        {
            "type": "GOOGLE_CALENDAR_STARTED",
            "task_id": task_id,
        },
    )

    gcal_response = await gcal_service.create_event_with_meet(func_call)

    meeting_link = gcal_response.get("meeting_link")

    # Persist record to Database
    async with AsyncSessionLocal() as session:

        record = CalendarEventDB(
            user_id=user_id,
            task_id=task_id,
            request_text=request_text,
            summary=func_call.summary,
            start_time=(func_call.start.date_time),
            end_time=(func_call.end.date_time),
            attendees=[str(email) for email in func_call.attendees],
            meeting_link=meeting_link,
            google_event_id=(gcal_response.get("event_id")),
            status=(
                gcal_response.get(
                    "status",
                    "scheduled",
                )
            ),
            raw_function_call=(func_call.model_dump()),
        )

        session.add(record)

        await session.commit()

    result = {
        "function_call": (func_call.model_dump()),
        "google_calendar_event": (gcal_response),
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
    max_retries=5,
    acks_late=True,
)
def execute_calendar_schedule_task(
    self,
    user_id: int,
    request_text: str,
):

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

        status = getattr(
            exc.resp,
            "status",
            None,
        )

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
