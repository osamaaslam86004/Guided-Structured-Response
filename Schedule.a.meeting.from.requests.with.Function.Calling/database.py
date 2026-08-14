import json
from typing import Optional
from sqlmodel import Field, Session, SQLModel, create_engine

DATABASE_URL = "sqlite:///./calendar_events.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})


class CalendarEventDB(SQLModel, table=True):
  id: Optional[int] = Field(default=None, primary_key=True)
  request_text: str
  summary: str
  start_time: str
  end_time: str
  attendees_json: str
  status: str = "scheduled"
  raw_function_call_json: str


def init_db():
  SQLModel.metadata.create_all(engine)


def get_db_session():
  with Session(engine) as session:
    yield session