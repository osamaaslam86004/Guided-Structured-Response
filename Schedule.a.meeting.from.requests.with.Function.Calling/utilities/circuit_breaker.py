import time
import logging
import redis
from typing import Optional

from config.settings import settings
from utilities.security import append_audit_event, get_current_correlation_id

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
        append_audit_event(
            "circuit_breaker_tripped",
            actor_id="system",
            tenant_id="system",
            action="circuit_breaker.trip",
            resource=provider_name,
            metadata={"ttl_seconds": ttl_seconds, "state": "tripped"},
            correlation_id=get_current_correlation_id(),
        )
    except Exception as exc:
        logger.exception("Failed to trip circuit for %s: %s", provider_name, exc)


def clear(provider_name: str) -> None:
    try:
        _redis.delete(_key(provider_name))
        append_audit_event(
            "circuit_breaker_cleared",
            actor_id="system",
            tenant_id="system",
            action="circuit_breaker.clear",
            resource=provider_name,
            metadata={"state": "cleared"},
            correlation_id=get_current_correlation_id(),
        )
    except Exception:
        pass
