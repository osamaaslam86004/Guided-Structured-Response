# main.py

from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from contextlib import asynccontextmanager

from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware
from fastapi.middleware.cors import CORSMiddleware

from config.settings import settings
from config.limiter import limiter
from config.logging_config import setup_logging
from config.database import close_db

from routes.auth import router as auth_router
from routes.event_parser import event_parser_router
from routes.meeting_scheduler import router as meeting_scheduler_router
from routes.task_status import router as task_status_router
from routes.websocket_events import router as websocket_router
from routes.admin_analytics import router as admin_analytics_router
from routes.dlq_admin import router as dlq_admin_router

from middleware.tenant_guard import TenantGuardMiddleware
from middleware.request_correlation import RequestCorrelationMiddleware

# Initialize global logging before creating the app
setup_logging(log_level=settings.app.log_level, environment=settings.app.env)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Run any startup tasks (e.g., warm up Redis cache)
    yield
    # Shutdown: Clean up connection pools gracefully
    await close_db()


app = FastAPI(
    title=settings.app.name,
    version=settings.app.api_v1_prefix,
    description=settings.app.description,
    lifespan=lifespan,
)

# Attach Limiter State & Error Handler
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    SessionMiddleware,
    secret_key=settings.security.session_secret,
    https_only=(settings.app.env == "production"),
    same_site="lax",
)

app.add_middleware(
    CORSMiddleware,
    # Convert Pydantic AnyHttpUrl objects to strings for Middleware
    allow_origins=[str(origin) for origin in settings.security.allow_origins],
    allow_credentials=settings.security.allow_credentials,
    allow_methods=settings.security.allow_methods,
    allow_headers=settings.security.allow_headers,
)

app.add_middleware(TenantGuardMiddleware)
app.add_middleware(RequestCorrelationMiddleware)

app.include_router(auth_router)
app.include_router(event_parser_router)
app.include_router(meeting_scheduler_router)
app.include_router(task_status_router)
app.include_router(websocket_router)
app.include_router(admin_analytics_router)
app.include_router(dlq_admin_router)
