# gcloud_service.py
# That gives you actual multi-tenancy instead of a database column pretending to be multi-tenancy.

import json
import os
import uuid
import redis
from datetime import datetime
from typing import Any, Dict, Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import OAuthTokenDB

# Initialize Redis client
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
redis_client = redis.Redis(
    host=REDIS_HOST, port=REDIS_PORT, db=2, decode_responses=True
)

CACHE_TTL_SECONDS = 3600  # 1 hour cache window
DEFAULT_TOKEN_URI = "https://oauth2.googleapis.com/token"


class GoogleCalendarService:

    def __init__(self, user_id: int, session: AsyncSession):

        self.user_id = user_id
        self.session = session
        self.calendar_id = os.getenv("GOOGLE_CALENDAR_ID", "primary")

    async def _get_credentials(self) -> Optional[Credentials]:

        cache_key = f"google_oauth_token:{self.user_id}"

        # Step 1: Check Redis Cache
        cached_token_data = redis_client.get(cache_key)
        token_dict = None

        if cached_token_data:
            token_dict = json.loads(cached_token_data)

            expiry_raw = token_dict.get("expiry")
            expiry_dt = datetime.fromisoformat(expiry_raw) if expiry_raw else None

            credentials = Credentials(
                token=token_dict.get("access_token"),
                refresh_token=token_dict.get("refresh_token"),
                token_uri=token_dict.get("token_uri"),
                client_id=token_dict.get("client_id"),
                client_secret=token_dict.get("client_secret"),
                scopes=token_dict.get("scopes"),
                expiry=expiry_dt,
            )
            return credentials

        # Step 2: Fetch from Database
        result = await self.session.execute(
            select(OAuthTokenDB).where(OAuthTokenDB.user_id == self.user_id)
        )

        token = result.scalar_one_or_none()

        if not token:
            return None

        token_uri = getattr(token, "token_uri", None) or DEFAULT_TOKEN_URI

        credentials = Credentials(
            token=token.access_token,
            refresh_token=(token.refresh_token),
            token_uri=(token.token_uri),
            client_id=(token.client_id),
            client_secret=(token.client_secret),
            scopes=token.scopes,
            expiry=token.expiry,
        )

        # Refresh the token if it's expired
        if credentials.expired and credentials.refresh_token:

            credentials.refresh(Request())

            token.access_token = credentials.token

            # Update the expiry in the database
            token.expiry = credentials.expiry

            await self.session.commit()

            # Build clean serializable dict for Redis Cache
            cache_payload = {
                "access_token": credentials.token,
                "refresh_token": credentials.refresh_token,
                "token_uri": credentials.token_uri,
                "client_id": credentials.client_id,
                "client_secret": credentials.client_secret,
                "scopes": credentials.scopes,
                "expiry": (
                    credentials.expiry.isoformat() if credentials.expiry else None
                ),
            }

            # Write back to Redis Cache
            redis_client.set(cache_key, json.dumps(cache_payload), ex=CACHE_TTL_SECONDS)

        return credentials

    async def create_event_with_meet(self, event_data) -> Dict[str, Any]:

        credentials = await self._get_credentials()

        if not credentials:

            raise RuntimeError("Google Calendar authentication " "required")

        service = build(
            "calendar",
            "v3",
            credentials=credentials,
            cache_discovery=False,
        )

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
            "attendees": [{"email": str(email)} for email in event_data.attendees],
            "conferenceData": {
                "createRequest": {
                    "requestId": uuid.uuid4().hex,
                    "conferenceSolutionKey": {"type": "hangoutsMeet"},
                }
            },
        }

        created_event = (
            service.events()
            .insert(
                calendarId=self.calendar_id,
                body=event_body,
                conferenceDataVersion=1,
                sendUpdates=(event_data.send_updates.value),
            )
            .execute()
        )

        conference_data = created_event.get(
            "conferenceData",
            {},
        )

        entry_points = conference_data.get(
            "entryPoints",
            [],
        )

        meeting_link = next(
            (
                ep.get("uri")
                for ep in entry_points
                if ep.get("entryPointType") == "video"
            ),
            created_event.get("hangoutsLink"),
        )

        return {
            "event_id": created_event.get("id"),
            "html_link": created_event.get("htmlLink"),
            "meeting_link": meeting_link,
            "status": created_event.get("status"),
        }


async def get_gcal_service(
    user_id: int, session: AsyncSession
) -> GoogleCalendarService:

    return GoogleCalendarService(user_id=user_id, session=session)
