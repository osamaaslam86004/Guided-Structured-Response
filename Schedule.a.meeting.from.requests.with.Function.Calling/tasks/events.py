# events.py (Redis event publisher)

import json
import redis
from config.settings import settings

redis_client = redis.Redis.from_url(settings.redis.url, decode_responses=True)


def publish_task_event(
    task_id: str,
    event: dict,
) -> None:

    channel = f"task_events:{task_id}"

    redis_client.publish(channel, json.dumps(event))
