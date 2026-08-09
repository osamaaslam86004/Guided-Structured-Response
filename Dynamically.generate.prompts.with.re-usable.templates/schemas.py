from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator


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
  summary: str = Field(..., min_length=5, max_length=100,
                       description=(
                         "Direct 1-sentence summary of the user's feedback text. DO NOT explain \
                          'your reasoning' or mention 'the user'"))
  key_aspects: List[ActionableAspect] = Field(
      default_factory=list, description="Key features evaluated"
  )

  @field_validator("confidence_score", mode="before")
  @classmethod
  def normalize_confidence(cls, v):
    # Automatically convert percentage scores (e.g., 90) to decimal floats (0.90)
    if isinstance(v, (int, float)) and v > 1.0:
      return v / 100.0
    return v


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