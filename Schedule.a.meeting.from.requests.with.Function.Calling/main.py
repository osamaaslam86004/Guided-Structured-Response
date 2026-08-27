# main.py

from contextlib import asynccontextmanager

from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware
from fastapi.middleware.cors import CORSMiddleware

from config.settings import settings
from config.logging_config import setup_logging

from config.database import close_db

from routes.auth import router as auth_router
from routes.event_parser import event_parser_router
from routes.meeting_scheduler import router as meeting_scheduler_router
from routes.task_status import router as task_status_router
from routes.websocket_events import router as websocket_router
from routes.admin_analytics import router as admin_analytics_router


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
    allow_headers=settings.security.allow_headers
)

app.include_router(auth_router)
app.include_router(event_parser_router)
app.include_router(meeting_scheduler_router)
app.include_router(task_status_router)
app.include_router(websocket_router)
app.include_router(admin_analytics_router)