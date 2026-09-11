# routes/meeting_scheduler.py
# Now the worker knows exactly whose Google Calendar should be used.


from fastapi import APIRouter, Depends, HTTPException, status
from datetime import datetime
import math

from config.cache import get_redis_client
from config.settings import settings
from utilities.tokenizer import count_tokens
from utilities.redis_scripts import atomic_consume

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

    # Dual-bucket enforcement via settings
    rl = settings.rate_limiting

    REQUEST_LIMIT = rl.requests_per_minute
    REQUEST_WINDOW = rl.request_window_seconds

    TOKEN_LIMIT = rl.tokens_per_hour
    TOKEN_WINDOW = rl.token_window_seconds

    # Token estimate using tokenizer
    token_estimate = max(1, count_tokens(payload.request_text))

    redis_client = await get_redis_client()

    now = int(datetime.utcnow().timestamp())
    req_min = now // REQUEST_WINDOW
    token_hour = now // TOKEN_WINDOW

    req_key = f"req_bucket:{user.id}:{req_min}"
    token_key = f"token_used:{user.id}:{token_hour}"

    # Atomic consume both buckets using Lua script
    success, new_req, new_token = await atomic_consume(
        redis_client,
        req_key,
        token_key,
        REQUEST_LIMIT,
        TOKEN_LIMIT,
        token_estimate,
        REQUEST_WINDOW,
        TOKEN_WINDOW,
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded (requests or token quota)",
        )

    task = execute_calendar_schedule_task.delay(
        user_id=user.id,
        request_text=payload.request_text,
    )

    return TaskStatusResponse(
        task_id=task.id,
        status="PENDING",
    )
