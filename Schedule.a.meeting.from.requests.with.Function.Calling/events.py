# events.py (Redis event publisher)

import json
import os

import redis

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))


redis_client = redis.Redis(
    host=REDIS_HOST, port=REDIS_PORT, db=3, decode_responses=True
)


def publish_task_event(
    task_id: str,
    event: dict,
) -> None:

    channel = f"task_events:{task_id}"

    redis_client.publish(channel, json.dumps(event))
