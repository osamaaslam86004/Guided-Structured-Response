import hashlib
import json
from typing import Optional
import redis.asyncio as aioredis
from config.settings import settings

# Async Redis Client
redis_client = aioredis.from_url(settings.redis.async_url, decode_responses=True)


def generate_cache_key(request_text: str) -> str:
    return f"cal_schedule:{hashlib.md5(request_text.strip().encode()).hexdigest()}"


async def get_cached_function_call(cache_key: str) -> Optional[dict]:
    try:
        cached_data = await redis_client.get(cache_key)
        if cached_data:
            return json.loads(cached_data)
    except Exception as e:
        print(f"Redis Cache Read Error: {e}")
    return None


async def set_cached_function_call(
    cache_key: str, data: dict, expire_seconds: int = 86400
):
    try:
        await redis_client.set(
            cache_key,
            json.dumps(data),
            ex=expire_seconds,
        )
    except Exception as e:
        print(f"Redis Cache Write Error: {e}")
