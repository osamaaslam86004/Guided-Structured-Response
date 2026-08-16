from database import init_db
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager


@asynccontextmanager
async def lifespan(app: FastAPI):
  init_db()  # Initialize database tables on startup
  yield


app = FastAPI(
    title="Google Calendar Function Calling Engine",
    version="3.0.0",
    description=(
        "Outlines-powered engine for extracting Google Calendar tool parameters"
        " from text."
    ),
    lifespan=lifespan,
)


# Enable CORS so your Vercel frontend can securely communicate with this backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Replace with your Vercel production URL later
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include route modules
from routes.event_parser import event_parser_router
from routes.meeting_scheduler import meeting_scheduler_router
from routes.task_status import task_status_router

app.include_router(event_parser_router)
app.include_router(meeting_scheduler_router)
app.include_router(task_status_router)