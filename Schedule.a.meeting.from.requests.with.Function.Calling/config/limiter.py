# config/limiter.py
from slowapi import Limiter
from slowapi.util import get_remote_address
from fastapi import Request
from config.settings import settings


def get_identifier(request: Request) -> str:
    """
    Identifies the client by user ID (if authenticated) or IP address.
    """
    # 1. Prefer authenticated user ID (stored in session or request state)
    user_id = request.session.get("user_id") if hasattr(request, "session") else None
    if user_id:
        return f"user:{user_id}"

    # 2. Fall back to remote IP address
    return f"ip:{get_remote_address(request)}"


limiter = Limiter(
    key_func=get_identifier,
    storage_uri=settings.redis.async_url,  # Uses your Redis instance
    default_limits=["100/minute"],  # Default global rate limit
)
