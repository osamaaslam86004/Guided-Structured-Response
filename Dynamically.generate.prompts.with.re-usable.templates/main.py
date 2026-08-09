from typing import List
from cache import generate_cache_key, get_cached_analysis, set_cached_analysis
from celery.result import AsyncResult
from database import ReviewAnalysisDB, engine, init_db
from engine import get_sentiment_engine
from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException
from schemas import (
    AnalysisRecordResponse,
    BatchReviewRequest,
    SentimentAnalysisOutput,
    SingleReviewRequest,
    TaskStatusResponse,
)
from sqlmodel import Session
from tasks import process_batch_reviews

app = FastAPI(
    title="Amazon Review Sentiment Analysis API",
    version="2.0.0",
    description="Production-grade Outlines dynamic template sentiment engine.",
)


@app.on_event("startup")
def on_startup():
  init_db()


@app.post("/api/v1/analyze", response_model=AnalysisRecordResponse)
def analyze_single_review(
    request: SingleReviewRequest,
):
  cache_key = generate_cache_key(
      request.product_category, request.review_title, request.text
  )
  cached_result = get_cached_analysis(cache_key)

  if cached_result:
    return AnalysisRecordResponse(
        id=0,
        cached=True,
        analysis=SentimentAnalysisOutput.model_validate(cached_result),
    )

  engine_instance = get_sentiment_engine()
  analysis = engine_instance.analyze_review(
      text=request.text,
      product_category=request.product_category,
      content_type=request.content_type,
      review_title=request.review_title,
  )

  # Cache result
  set_cached_analysis(cache_key, analysis.model_dump())

  # DB Persistence
  with Session(engine) as session:
    db_record = ReviewAnalysisDB(
        product_category=request.product_category,
        review_text=request.text,
        sentiment=analysis.sentiment.value,
        confidence_score=analysis.confidence_score,
        summary=analysis.summary,
        raw_analysis_json=analysis.model_dump_json(),
    )
    session.add(db_record)
    session.commit()
    session.refresh(db_record)
    record_id = db_record.id

  return AnalysisRecordResponse(
      id=record_id, cached=False, analysis=analysis
  )


@app.post("/api/v1/batch-analyze", response_model=TaskStatusResponse)
def analyze_batch_reviews(request: BatchReviewRequest):
  reviews_data = [r.model_dump() for r in request.reviews]
  task = process_batch_reviews.delay(reviews_data)
  return TaskStatusResponse(task_id=task.id, status="PENDING")


@app.get("/api/v1/tasks/{task_id}", response_model=TaskStatusResponse)
def get_task_status(task_id: str):
  task_result = AsyncResult(task_id)

  if task_result.state == "PENDING":
    return TaskStatusResponse(task_id=task_id, status="PENDING")
  elif task_result.state == "PROGRESS":
    return TaskStatusResponse(
        task_id=task_id, status=f"PROGRESS ({task_result.info})"
    )
  elif task_result.state == "SUCCESS":
    return TaskStatusResponse(
        task_id=task_id, status="SUCCESS", result=task_result.result
    )
  else:
    return TaskStatusResponse(task_id=task_id, status=task_result.state)