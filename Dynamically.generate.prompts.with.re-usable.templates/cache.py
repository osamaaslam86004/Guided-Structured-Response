import hashlib
import json
import os
from typing import Optional
import redis

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))

redis_client = redis.Redis(
    host=REDIS_HOST, port=REDIS_PORT, db=0, decode_responses=True
)


def generate_cache_key(category: str, title: str, text: str) -> str:
  raw_str = f"{category}:{title}:{text}"
  return f"sentiment:{hashlib.md5(raw_str.encode()).hexdigest()}"


def get_cached_analysis(cache_key: str) -> Optional[dict]:
  try:
    cached_data = redis_client.get(cache_key)
    if cached_data:
      return json.loads(cached_data)
  except Exception as e:
    print(f"Redis Cache Read Error: {e}")
  return None


def set_cached_analysis(
    cache_key: str, data: dict, expire_seconds: int = 86400
):
  try:
    redis_client.setex(cache_key, expire_seconds, json.dumps(data))
  except Exception as e:
    print(f"Redis Cache Write Error: {e}")