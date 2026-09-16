from typing import List, Optional

import json
import logging

from fastapi import APIRouter, HTTPException, status, Depends, Header

from config.limiter import limiter
from config.settings import settings
from dlq import redis_client
from celery_app import celery_app

from models.dlq_db import DLQEntry, RequeueResponse

logger = logging.getLogger(__name__)


def require_admin(
    x_admin_key: Optional[str] = Header(None),
    authorization: Optional[str] = Header(None),
):
    """Simple admin auth dependency.

    Accepts either an `X-Admin-Key` header or `Authorization: Bearer <key>`.
    The header value must match `settings.security.app_master_key`.
    """

    expected = settings.security.app_master_key

    # Check X-Admin-Key first
    if x_admin_key and x_admin_key == expected:
        return True

    # Check Authorization header (Bearer)
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ", 1)[1]
        if token == expected:
            return True

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED, detail="Admin auth required"
    )


router = APIRouter(
    prefix="/admin/dlq", tags=["Admin"], dependencies=[Depends(require_admin)]
)


@router.get("/", response_model=List[DLQEntry])
@limiter.limit("30/minute")
def list_dlq():
    """List entries in the Redis DLQ."""
    raw_list = redis_client.lrange(settings.redis.dlq_key, 0, -1)
    entries: List[DLQEntry] = []
    for raw in raw_list:
        try:
            payload = json.loads(raw)
            entries.append(DLQEntry(**payload))
        except Exception:
            logger.exception("Failed to parse DLQ entry: %s", raw)
    return entries


@router.post("/requeue", response_model=RequeueResponse)
@limiter.limit("20/minute")
def requeue_dlq_entry(task_id: str):
    """Requeue a single DLQ entry back to the Celery task queue.

    The client supplies the original `task_id` that was pushed into the DLQ.
    """
    raw_list = redis_client.lrange(settings.redis.dlq_key, 0, -1)

    for raw in raw_list:
        try:
            payload = json.loads(raw)
        except Exception:
            continue

        if payload.get("task_id") == task_id:
            user_id = payload.get("user_id")
            request_text = payload.get("request_text")

            # Re-dispatch the task to Celery
            try:
                async_result = celery_app.send_task(
                    "tasks.execute_calendar_schedule_task",
                    args=[user_id, request_text],
                )
                new_id = getattr(async_result, "id", None)

                # Remove the DLQ entry
                redis_client.lrem(settings.redis.dlq_key, 1, raw)

                return RequeueResponse(
                    original_task_id=task_id, new_task_id=new_id, status="requeued"
                )

            except Exception as exc:
                logger.exception("Failed to requeue DLQ entry %s: %s", task_id, exc)
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to requeue task",
                )

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"DLQ entry with task_id {task_id} not found",
    )


@router.post("/requeue_all")
@limiter.limit("5/minute")
def requeue_all_dlq_entries():
    """Requeue all DLQ entries. Returns summary of requeued tasks."""
    raw_list = redis_client.lrange(settings.redis.dlq_key, 0, -1)
    summary = []

    for raw in raw_list:
        try:
            payload = json.loads(raw)
        except Exception:
            logger.exception("Skipping unparsable DLQ payload: %s", raw)
            continue

        task_id = payload.get("task_id")
        user_id = payload.get("user_id")
        request_text = payload.get("request_text")

        try:
            async_result = celery_app.send_task(
                "tasks.execute_calendar_schedule_task",
                args=[user_id, request_text],
            )
            new_id = getattr(async_result, "id", None)
            summary.append(
                {
                    "original_task_id": task_id,
                    "new_task_id": new_id,
                    "status": "requeued",
                }
            )
            # Remove processed item
            redis_client.lrem(settings.redis.dlq_key, 1, raw)
        except Exception:
            logger.exception("Failed to requeue DLQ entry: %s", task_id)
            summary.append(
                {"original_task_id": task_id, "new_task_id": None, "status": "failed"}
            )

    return {"count": len(summary), "results": summary}


@router.delete("/{task_id}")
@limiter.limit("10/minute")
def delete_dlq_entry(task_id: str):
    """Delete a DLQ entry without requeueing."""
    raw_list = redis_client.lrange(settings.redis.dlq_key, 0, -1)

    for raw in raw_list:
        try:
            payload = json.loads(raw)
        except Exception:
            continue

        if payload.get("task_id") == task_id:
            redis_client.lrem(settings.redis.dlq_key, 1, raw)
            return {"deleted": task_id}

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"DLQ entry with task_id {task_id} not found",
    )
