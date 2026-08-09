import json
from typing import Optional
from sqlmodel import Field, Session, SQLModel, create_engine

DATABASE_URL = "sqlite:///./reviews_sentiment.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})


class ReviewAnalysisDB(SQLModel, table=True):
  id: Optional[int] = Field(default=None, primary_key=True)
  product_category: str
  review_text: str
  sentiment: str
  confidence_score: float
  summary: str
  raw_analysis_json: str


def init_db():
  SQLModel.metadata.create_all(engine)


def get_db_session():
  with Session(engine) as session:
    yield session