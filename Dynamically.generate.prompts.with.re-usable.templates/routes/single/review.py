from fastapi import APIRouter
from sqlalchemy.orm import Session
from schemas import (
    AnalysisRecordResponse,
    SentimentAnalysisOutput,
    SingleReviewRequest,
)
from cache import generate_cache_key, get_cached_analysis, set_cached_analysis
from database import ReviewAnalysisDB, engine
from engine import get_sentiment_engine


router = APIRouter()


@router.post("/api/v1/analyze", response_model=AnalysisRecordResponse)
def analyze_single_review(request: SingleReviewRequest):
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
        review_title=request.review_title
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
            raw_analysis_json=analysis.model_dump_json()
            )
        session.add(db_record)
        session.commit()
        session.refresh(db_record)
        record_id = db_record.id

    return AnalysisRecordResponse(id=record_id, cached=False, analysis=analysis)


@router.get("/health")
def health_check():
        return {"status": "healthy"}
