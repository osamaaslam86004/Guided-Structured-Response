from fastapi import APIRouter
from schemas import (
    TaskStatusResponse,
    UserScheduleRequest,
)
from tasks import execute_calendar_schedule_task

meeting_scheduler_router = APIRouter()

@meeting_scheduler_router.post("/api/v1/async-schedule", response_model=TaskStatusResponse)
def async_schedule_meeting(payload: UserScheduleRequest):
  task = execute_calendar_schedule_task.delay(payload.request_text)
  return TaskStatusResponse(task_id=task.id, status="PENDING")


