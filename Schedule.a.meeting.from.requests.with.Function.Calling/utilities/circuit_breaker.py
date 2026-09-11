import time
import logging
import redis
from typing import Optional

from config.settings import settings

logger = logging.getLogger(__name__)

# Sync Redis client for circuit breaker operations (fast, simple)
_redis = redis.Redis.from_url(settings.redis.url, decode_responses=True)


def _key(provider_name: str) -> str:
    return f"circuit_breaker:{provider_name}"


def is_tripped(provider_name: str) -> bool:
    """Return True if circuit for provider_name is currently tripped."""
    val = _redis.get(_key(provider_name))
    return val is not None


def trip(provider_name: str, ttl_seconds: int = 60) -> None:
    """Trip the circuit for provider_name for ttl_seconds."""
    try:
        _redis.set(_key(provider_name), int(time.time()), ex=ttl_seconds)
        logger.warning(
            "Circuit tripped for provider %s for %s seconds", provider_name, ttl_seconds
        )
    except Exception as exc:
        logger.exception("Failed to trip circuit for %s: %s", provider_name, exc)


def clear(provider_name: str) -> None:
    try:
        _redis.delete(_key(provider_name))
    except Exception:
        pass
