import hashlib
import json
import os
from typing import Optional
import redis

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))

redis_client = redis.Redis(
    host=REDIS_HOST, port=REDIS_PORT, db=1, decode_responses=True
)


def generate_cache_key(request_text: str) -> str:
    return f"cal_schedule:{hashlib.md5(request_text.strip().encode()).hexdigest()}"


def get_cached_function_call(cache_key: str) -> Optional[dict]:
    try:
        cached_data = redis_client.get(cache_key)
        if cached_data:
            return json.loads(cached_data)
    except Exception as e:
        print(f"Redis Cache Read Error: {e}")
    return None


def set_cached_function_call(cache_key: str, data: dict, expire_seconds: int = 86400):
    try:
        redis_client.set(
            cache_key,
            json.dumps(data),
            ex=expire_seconds,
        )
    except Exception as e:
        print(f"Redis Cache Write Error: {e}")
