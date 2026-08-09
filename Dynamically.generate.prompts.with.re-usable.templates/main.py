from contextlib import asynccontextmanager
from database import init_db
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
  init_db()  # Initialize database tables on startup
  yield


app = FastAPI(
  lifespan=lifespan,
  title="Amazon Review Sentiment Analysis API",
  version="2.0.0",
  description="Production-grade Outlines dynamic template sentiment engine.",
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
from routes.single.review import router as single_router
from routes.batch.review import router as batch_router

app.include_router(single_router)
app.include_router(batch_router)

