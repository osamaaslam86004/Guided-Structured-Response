import hashlib
import json
import os
import redis
from sqlmodel import Field, Session, SQLModel, create_engine

# Database setup (SQLite by default)
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./tickets.db")
db_engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

# Redis setup
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)


# Database Table Model
class TicketRecord(SQLModel, table=True):
  id: Optional[int] = Field(default=None, primary_key=True)
  ticket_text: str
  analysis_json: str  # Stored as JSON string


def init_db():
  SQLModel.metadata.create_all(db_engine)


# Helper functions
def get_cache_key(text: str) -> str:
  """Generates MD5 hash of ticket text to use as Redis key."""
  return f"ticket_cache:{hashlib.md5(text.strip().encode()).hexdigest()}"


def get_cached_analysis(text: str) -> Optional[dict]:
  try:
    cached = redis_client.get(get_cache_key(text))
    return json.loads(cached) if cached else None
  except redis.RedisError:
    return None  # Fallback gracefully if Redis is unreachable


def set_cached_analysis(text: str, data: dict, ttl: int = 86400):
  try:
    redis_client.setex(get_cache_key(text), ttl, json.dumps(data))
  except redis.RedisError:
    pass  # Ignore cache write errors


def save_ticket_to_db(text: str, analysis_dict: dict) -> TicketRecord:
  record = TicketRecord(
      ticket_text=text, analysis_json=json.dumps(analysis_dict)
  )
  with Session(db_engine) as session:
    session.add(record)
    session.commit()
    session.refresh(record)
    return record