# routes/meeting_scheduler.py
# Now the worker knows exactly whose Google Calendar should be used.


from fastapi import APIRouter, Depends

from auth import get_current_user
from database import UserDB
from schemas import (
    TaskStatusResponse,
    UserScheduleRequest,
)

from tasks import execute_calendar_schedule_task


router = APIRouter()


@router.post(
    "/api/v1/async-schedule",
    response_model=TaskStatusResponse,
)
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

