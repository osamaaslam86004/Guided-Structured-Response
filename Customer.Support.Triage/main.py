from contextlib import asynccontextmanager
import json
from database import (
    get_cached_analysis,
    init_db,
    save_ticket_to_db,
    set_cached_analysis,
)
from engine import ProductionEngine, get_engine
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.concurrency import run_in_threadpool
from schemas import SupportTicketAnalysis, TicketRequest, TicketResponse


@asynccontextmanager
async def lifespan(app: FastAPI):
  init_db()  # Initialize database tables on startup
  yield


app = FastAPI(title="Outlines Production API", lifespan=lifespan)


# Enable CORS so your Vercel frontend can securely communicate with this backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Replace with your Vercel production URL later
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health_check():
    return {"status": "healthy"}


@app.post("/analyze-ticket", response_model=TicketResponse)
async def analyze_ticket(
    payload: TicketRequest, engine: ProductionEngine = Depends(get_engine)
):
  try:
    # 1. Check Redis Cache
    cached_data = get_cached_analysis(payload.ticket_text)
    if cached_data:
      analysis = SupportTicketAnalysis.model_validate(cached_data)
      db_record = save_ticket_to_db(
          payload.ticket_text, analysis.model_dump()
      )
      return TicketResponse(
          id=db_record.id,
          ticket_text=payload.ticket_text,
          cached=True,
          analysis=analysis,
      )

    # 2. Cache Miss -> Run CPU Inference
    analysis = await run_in_threadpool(
        engine.analyze, payload.ticket_text, payload.prompt
    )
    analysis_dict = analysis.model_dump()

    # 3. Cache Result in Redis & Save to Database
    set_cached_analysis(payload.ticket_text, analysis_dict)
    db_record = save_ticket_to_db(payload.ticket_text, analysis_dict)

    return TicketResponse(
        id=db_record.id,
        ticket_text=payload.ticket_text,
        cached=False,
        analysis=analysis,
    )

  except Exception as e:
    raise HTTPException(status_code=500, detail=str(e))