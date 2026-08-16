import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
import redis
from sqlmodel import Session, select

from database import OAuthTokenDB, engine
from schemas import ScheduleCalendarEventFunction

# Initialize Redis client
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
redis_client = redis.Redis(
    host=REDIS_HOST, port=REDIS_PORT, db=1, decode_responses=True
)

CACHE_TTL_SECONDS = 3600  # 1 hour cache window


class GoogleCalendarService:

  def __init__(self, user_email: str = "primary_user"):
    self.user_email = user_email
    self.calendar_id = os.getenv("GOOGLE_CALENDAR_ID", "primary")
    self.credentials = self._get_credentials()

    if self.credentials:
      self.service = build("calendar", "v3", credentials=self.credentials, cache_discovery=False)
    else:
      self.service = None
      print("Warning: No valid OAuth token found in Redis or SQLite database.")

  def _get_credentials(self) -> Optional[Credentials]:
    cache_key = f"google_oauth_token:{self.user_email}"

    # Step 1: Check Redis Cache
    cached_token_data = redis_client.get(cache_key)
    token_dict = None

    if cached_token_data:
      token_dict = json.loads(cached_token_data)
    else:
      # Step 2: Fallback to SQLite Database
      with Session(engine) as session:
        statement = select(OAuthTokenDB).where(
            OAuthTokenDB.user_email == self.user_email
        )
        db_token = session.exec(statement).first()

        if db_token:
          token_dict = {
              "token": db_token.access_token,
              "refresh_token": db_token.refresh_token,
              "token_uri": db_token.token_uri,
              "client_id": db_token.client_id,
              "client_secret": db_token.client_secret,
              "scopes": json.loads(db_token.scopes_json),
          }
          if db_token.expiry:
            token_dict["expiry"] = db_token.expiry

          # Write back to Redis Cache
          redis_client.setex(
              cache_key, CACHE_TTL_SECONDS, json.dumps(token_dict)
          )

    if not token_dict:
      return None

    # Parse expiration string to datetime object if present
    expiry_dt = None
    if token_dict.get("expiry"):
      expiry_dt = datetime.fromisoformat(token_dict["expiry"])

    creds = Credentials(
        token=token_dict.get("token"),
        refresh_token=token_dict.get("refresh_token"),
        token_uri=token_dict.get("token_uri"),
        client_id=token_dict.get("client_id"),
        client_secret=token_dict.get("client_secret"),
        scopes=token_dict.get("scopes"),
        expiry=expiry_dt,
    )

    # Step 3: Handle Automatic Refresh if Expired
    if creds.expired and creds.refresh_token:
      creds.refresh(Request())
      self._update_token_stores(creds)

    return creds

  def _update_token_stores(self, creds: Credentials) -> None:
    """Sync refreshed token back to both SQLite DB and Redis cache."""
    cache_key = f"google_oauth_token:{self.user_email}"
    expiry_str = creds.expiry.isoformat() if creds.expiry else None

    # Update SQLite DB
    with Session(engine) as session:
      statement = select(OAuthTokenDB).where(
          OAuthTokenDB.user_email == self.user_email
      )
      db_token = session.exec(statement).first()

      if db_token:
        db_token.access_token = creds.token
        if expiry_str:
          db_token.expiry = expiry_str
        session.add(db_token)
        session.commit()

    # Update Redis Cache
    token_dict = {
        "token": creds.token,
        "refresh_token": creds.refresh_token,
        "token_uri": creds.token_uri,
        "client_id": creds.client_id,
        "client_secret": creds.client_secret,
        "scopes": creds.scopes,
        "expiry": expiry_str,
    }
    redis_client.setex(cache_key, CACHE_TTL_SECONDS, json.dumps(token_dict))

  def create_event_with_meet(
      self, event_data: ScheduleCalendarEventFunction
  ) -> Dict[str, Any]:
    if not self.service:
      return {
          "event_id": f"mock_{uuid.uuid4().hex[:8]}",
          "html_link": "https://calendar.google.com/calendar/r/eventedit",
          "meeting_link": f"https://meet.google.com/{uuid.uuid4().hex[:3]}-{uuid.uuid4().hex[:4]}-{uuid.uuid4().hex[:3]}",
          "status": "confirmed_mock",
      }

    event_body = {
        "summary": event_data.summary,
        "description": event_data.description,
        "location": event_data.location,
        "start": {
            "dateTime": event_data.start.date_time,
            "timeZone": event_data.start.time_zone,
        },
        "end": {
            "dateTime": event_data.end.date_time,
            "timeZone": event_data.end.time_zone,
        },
        "attendees": [{"email": email} for email in event_data.attendees],
        "conferenceData": {
            "createRequest": {
                "requestId": f"req_{uuid.uuid4().hex}",
                "conferenceSolutionKey": {"type": "hangoutsMeet"},
            }
        },
    }

    created_event = (
        self.service.events()
        .insert(
            calendarId=self.calendar_id,
            body=event_body,
            conferenceDataVersion=1,
            sendUpdates=event_data.send_updates.value,
        )
        .execute()
    )

    conference_data = created_event.get("conferenceData", {})
    entry_points = conference_data.get("entryPoints", [])
    meeting_link = next(
        (ep.get("uri") for ep in entry_points if ep.get("entryPointType") == "video"),
        created_event.get("hangoutsLink"),
    )

    return {
        "event_id": created_event.get("id"),
        "html_link": created_event.get("htmlLink"),
        "meeting_link": meeting_link,
        "status": created_event.get("status"),
    }


_gcal_service_instance = None

def get_gcal_service() -> GoogleCalendarService:
    global _gcal_service_instance
    if _gcal_service_instance is None:
        _gcal_service_instance = GoogleCalendarService()
    return _gcal_service_instance