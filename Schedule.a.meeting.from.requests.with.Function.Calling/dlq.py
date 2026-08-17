# dlq.py

import json
import os
from datetime import datetime, timezone

import redis

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))


redis_client = redis.Redis(
    host=REDIS_HOST,
    port=REDIS_PORT,
    db=4,
    decode_responses=True,
)


DLQ_KEY = os.getenv("DLQ_KEY")
if not DLQ_KEY:
    raise ValueError("DLQ_KEY environment variable is not set.")


def push_dead_letter(
    task_id: str,
    user_id: int,
    request_text: str,
    error: str,
):

    payload = {
        "task_id": task_id,
        "user_id": user_id,
        "request_text": request_text,
        "error": error,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    redis_client.rpush(
        DLQ_KEY,
        json.dumps(payload),
    )
