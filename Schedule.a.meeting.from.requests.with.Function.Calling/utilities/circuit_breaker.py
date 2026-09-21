import time
import logging
import redis
import json
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


def set_breaker_policy(
    provider_name: str,
    *,
    open_threshold: int = 5,
    reset_timeout_seconds: int = 60,
    ttl_seconds: int | None = None,
) -> dict:
    """Store dynamic breaker policy values in Redis so the system can adapt without a redeploy."""
    ttl_seconds = ttl_seconds or settings.rate_limit.hot_reload_ttl_seconds
    policy = {
        "provider": provider_name,
        "open_threshold": int(open_threshold),
        "reset_timeout_seconds": int(reset_timeout_seconds),
        "ttl_seconds": int(ttl_seconds),
        "updated_at": int(time.time()),
    }
    _redis.set(f"runtime:breaker:{provider_name}", json.dumps(policy), ex=ttl_seconds)
    append_audit_event(
        "circuit_breaker_policy_updated",
        actor_id="system",
        tenant_id="system",
        action="circuit_breaker.hot_reload",
        resource=provider_name,
        metadata=policy,
        correlation_id=get_current_correlation_id(),
    )
    return policy


def get_breaker_policy(provider_name: str) -> dict:
    raw = _redis.get(f"runtime:breaker:{provider_name}")
    if not raw:
        return {
            "provider": provider_name,
            "open_threshold": 5,
            "reset_timeout_seconds": 60,
        }
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        return {
            "provider": provider_name,
            "open_threshold": 5,
            "reset_timeout_seconds": 60,
        }
