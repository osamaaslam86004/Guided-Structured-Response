# routes/meeting_scheduler.py
# Now the worker knows exactly whose Google Calendar should be used.


from fastapi import APIRouter, Depends, HTTPException, status
from datetime import datetime
import math

from config.cache import get_redis_client

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

    # Dual-bucket enforcement
    REQUEST_LIMIT = 5
    REQUEST_WINDOW = 60  # seconds

    TOKEN_LIMIT = 50000
    TOKEN_WINDOW = 3600  # seconds (1 hour)

    # Rough token estimate: characters / 4
    token_estimate = max(1, math.ceil(len(payload.request_text) / 4))

    redis_client = await get_redis_client()

    now = int(datetime.utcnow().timestamp())
    req_min = now // REQUEST_WINDOW
    token_hour = now // TOKEN_WINDOW

    req_key = f"req_bucket:{user.id}:{req_min}"
    token_key = f"token_used:{user.id}:{token_hour}"

    # Increment request counter
    req_count = await redis_client.incr(req_key)
    if req_count == 1:
        await redis_client.expire(req_key, REQUEST_WINDOW)

    if req_count > REQUEST_LIMIT:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded: too many requests",
        )

    # Increment token counter atomically and check quota
    new_tokens = await redis_client.incrby(token_key, token_estimate)
    if new_tokens == token_estimate:
        await redis_client.expire(token_key, TOKEN_WINDOW)

    if new_tokens > TOKEN_LIMIT:
        # Revert token increment
        await redis_client.decrby(token_key, token_estimate)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Token quota exceeded for current window",
        )

    task = execute_calendar_schedule_task.delay(
        user_id=user.id,
        request_text=payload.request_text,
    )

    return TaskStatusResponse(
        task_id=task.id,
        status="PENDING",
    )
