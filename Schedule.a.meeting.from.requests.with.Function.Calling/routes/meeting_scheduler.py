# routes/meeting_scheduler.py
# Now the worker knows exactly whose Google Calendar should be used.


from fastapi import APIRouter, Depends

from config.limiter import limiter
from auth import get_current_user
from models.user_db import UserDB
from schemas import (
    TaskStatusResponse,
    UserScheduleRequest,
)
from tasks.google_calender_meeting import execute_calendar_schedule_task

router = APIRouter()


@router.post(
    "/api/v1/async-schedule",
    response_model=TaskStatusResponse,
)
@limiter.limit("5/minute;20/hour")  # Strict rate limit for LLM/Celery execution
async def async_schedule_meeting(
    payload: UserScheduleRequest,
    user: UserDB = Depends(get_current_user),
):

    task = execute_calendar_schedule_task.delay(
        user_id=user.id,
        request_text=payload.request_text,
    )

    return TaskStatusResponse(
        task_id=task.id,
        status="PENDING",
    )
