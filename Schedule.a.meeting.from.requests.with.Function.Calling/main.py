# main.py

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware
from fastapi.middleware.cors import CORSMiddleware

from database import init_db, close_db

from routes.auth import router as auth_router
from routes.event_parser import event_parser_router
from routes.meeting_scheduler import router as meeting_scheduler_router
from routes.task_status import router as task_status_router
from routes.websocket_events import router as websocket_router


@asynccontextmanager
async def lifespan(app: FastAPI):

    await init_db()

    yield

    await close_db()


app = FastAPI(
    title="Google Calendar Function Calling Engine",
    version="3.1.0",
    description=(
        "Multi-tenant scheduling backend powered by " "local structured generation."
    ),
    lifespan=lifespan,
)

# Set https_only=False for local HTTP testing
IS_PRODUCTION = os.getenv("ENVIRONMENT") == "production"

app.add_middleware(
    SessionMiddleware,
    secret_key=os.environ["SESSION_SECRET"],
    https_only=IS_PRODUCTION,
    same_site="lax",
)

# Parse explicit origin array instead of passing wildcards with credentials
raw_frontend_url = os.getenv("FRONTEND_URL", "http://127.0.0.1:8000")
allowed_origins = [url.strip() for url in raw_frontend_url.split(",")]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(auth_router)

app.include_router(event_parser_router)

app.include_router(meeting_scheduler_router)

app.include_router(task_status_router)

app.include_router(websocket_router)
