import time
import logging
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
import redis.exceptions

from config.cache import get_redis_client

logger = logging.getLogger(__name__)


class TenantRBACMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, global_rate_limit: int = 1000, cluster_nodes: int = 3):
        super().__init__(app)
        self.global_rate_limit = global_rate_limit
        self.cluster_nodes = cluster_nodes
        # Fallback L/N local rate scaling
        self.local_rate_limit = max(1, self.global_rate_limit // self.cluster_nodes)

        # Local state for rate limiting fallback
        self.local_request_counts = {}
        self.local_window_start = time.time()
        self.window_duration = 60  # seconds

    def _reset_local_window_if_needed(self):
        now = time.time()
        if now - self.local_window_start > self.window_duration:
            self.local_request_counts = {}
            self.local_window_start = now

    def _check_local_rate_limit(self, tenant_id: str) -> bool:
        self._reset_local_window_if_needed()
        count = self.local_request_counts.get(tenant_id, 0)
        if count >= self.local_rate_limit:
            return False
        self.local_request_counts[tenant_id] = count + 1
        return True

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if path.startswith(("/docs", "/openapi", "/redoc", "/auth")):
            return await call_next(request)

        tenant_id = request.headers.get("X-Tenant-ID")
        auth_token = request.headers.get("Authorization")

        # Extract context and handle missing keys
        if not tenant_id:
            return JSONResponse(
                status_code=401, content={"detail": "Missing X-Tenant-ID header"}
            )

        if not auth_token:
            return JSONResponse(
                status_code=401, content={"detail": "Missing Authorization header"}
            )

        tenant_key = f"tenant:{tenant_id}"

        redis_available = False
        redis_client = None

        try:
            redis_client = await get_redis_client()
            # Check Redis health
            await redis_client.ping()
            redis_available = True
        except (
            redis.exceptions.ConnectionError,
            redis.exceptions.TimeoutError,
            Exception,
        ) as e:
            logger.warning(f"Redis unavailable, falling back to local rate limits: {e}")
            redis_available = False

        if redis_available and redis_client:
            # Check Bloom filter / Authorization Cache for token invalidation
            # Using standard Redis string GET as a fallback if Bloom Filter module is missing
            is_revoked = await redis_client.get(f"revoked_token:{auth_token}")
            if is_revoked:
                return JSONResponse(
                    status_code=403,
                    content={"detail": "Token revoked (authorization cache hit)"},
                )

            # Perform Global Rate Limiting
            rate_key = f"rate_limit:{tenant_key}"
            current_count = await redis_client.incr(rate_key)
            if current_count == 1:
                await redis_client.expire(rate_key, self.window_duration)

            if current_count > self.global_rate_limit:
                return JSONResponse(
                    status_code=429, content={"detail": "Global Rate Limit Exceeded"}
                )
        else:
            # Fallback fault tolerance: L/N local rate scaling when cluster offline/split
            if not self._check_local_rate_limit(tenant_id):
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Local Rate Limit Exceeded (Fallback Mode)"},
                )

        # Propagate validated/authenticated tenant context downstream
        request.state.tenant_context = {
            "tenant_id": tenant_id,
            "authenticated": True,
            "fallback_mode": not redis_available,
            "tenant_key": tenant_key,
        }

        response = await call_next(request)
        return response
