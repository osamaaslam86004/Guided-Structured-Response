"""Adaptive dynamic throttling helpers.

This module provides a small integration point to adjust token-bucket refill
parameters in Redis based on observed provider metrics (latency, error rate).

The implementation is intentionally minimal: it stores a suggested refill
multiplier per provider in Redis so other parts of the system can read it and
apply throttling conservatively.
"""

from typing import Optional
import logging
import math

from config.settings import settings
from dlq import redis_client

logger = logging.getLogger(__name__)


def compute_refill_multiplier(p95_latency_ms: float, error_rate: float) -> float:
    """Compute a conservative multiplier in range (0.1, 1.0].

    - Higher latency and higher error rates reduce the multiplier.
    - This function is deliberately simple and deterministic so it is easy to
      reason about in production.
    """
    # Normalize values to reasonable ranges
    latency_factor = min(1.0, max(0.0, 300.0 / (p95_latency_ms + 1e-6)))
    error_factor = min(1.0, max(0.0, 1.0 - error_rate))

    # Geometric-like combination favors the lower (safer) signal
    raw = latency_factor * error_factor

    # Map into [0.1, 1.0] to avoid fully disabling traffic
    multiplier = max(0.1, min(1.0, raw))
    return multiplier


def set_provider_refill_multiplier(
    provider: str, multiplier: float, ttl_seconds: int = 300
) -> None:
    key = f"throttle:provider:{provider}:refill"
    try:
        redis_client.set(key, float(multiplier))
        if ttl_seconds:
            redis_client.expire(key, int(ttl_seconds))
        logger.info("Set refill multiplier for %s -> %s", provider, multiplier)
    except Exception:
        logger.exception("Failed to set refill multiplier for provider %s", provider)


def adjust_based_on_metrics(
    provider: str, p95_latency_ms: float, error_rate: float
) -> float:
    """Calculate multiplier and persist it to Redis. Returns the multiplier.

    Call this from monitoring hooks or admin endpoints when you observe
    provider degradations.
    """
    multiplier = compute_refill_multiplier(p95_latency_ms, error_rate)
    set_provider_refill_multiplier(provider, multiplier)
    return multiplier
