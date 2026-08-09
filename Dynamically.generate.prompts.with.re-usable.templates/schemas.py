from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field


class SentimentType(str, Enum):
  POSITIVE = "Positive"
  NEGATIVE = "Negative"
  NEUTRAL = "Neutral"


class ActionableAspect(BaseModel):
  feature: str = Field(
      ..., description="Product feature mentioned (e.g., Battery, Screen, Fit)"
  )
  sentiment: SentimentType


class SentimentAnalysisOutput(BaseModel):
  sentiment: SentimentType = Field(..., description="Overall review sentiment")
  confidence_score: float = Field(
      ..., ge=0.0, le=1.0, description="Confidence rating between 0 and 1"
  )
  summary: str = Field(
      ..., max_length=120, description="Concise summary of the review text"
  )
  key_aspects: List[ActionableAspect] = Field(
      default_factory=list, description="Key features evaluated"
  )


class SingleReviewRequest(BaseModel):
  product_category: str = Field(
      default="E-Commerce Product", example="Electronics"
  )
  content_type: str = Field(default="user review", example="customer review")
  review_title: Optional[str] = Field(default="", example="Great value!")
  text: str = Field(
      ..., example="The camera quality is incredible, but battery life is poor."
  )


class BatchReviewRequest(BaseModel):
  reviews: List[SingleReviewRequest]


class AnalysisRecordResponse(BaseModel):
  id: int
  cached: bool
  analysis: SentimentAnalysisOutput


class TaskStatusResponse(BaseModel):
  task_id: str
  status: str
  result: Optional[List[SentimentAnalysisOutput]] = None