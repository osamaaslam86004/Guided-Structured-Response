from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, EmailStr, Field


class SendUpdatesOption(str, Enum):
  ALL = "all"
  EXTERNAL_ONLY = "externalOnly"
  NONE = "none"


class CalendarEventDateTime(BaseModel):
  date_time: str = Field(
      ...,
      description="Start or end time in ISO 8601 format (e.g. '2026-08-20T14:00:00Z')",
  )
  time_zone: str = Field(
      default="UTC", description="Timezone identifier, e.g., 'America/New_York' or 'UTC'"
  )


class ScheduleCalendarEventFunction(BaseModel):
  """Function calling schema for creating a Google Calendar meeting event."""

  summary: str = Field(
      ...,
      min_length=3,
      max_length=100,
      description="Title or summary of the meeting event",
  )
  description: Optional[str] = Field(
      default="", description="Detailed agenda or notes for the meeting"
  )
  location: Optional[str] = Field(
      default="", description="Physical location or video call link"
  )
  start: CalendarEventDateTime = Field(..., description="Meeting start date and time")
  end: CalendarEventDateTime = Field(..., description="Meeting end date and time")
  attendees: List[EmailStr] = Field(
      default_factory=list, description="List of participant email addresses"
  )
  send_updates: SendUpdatesOption = Field(
      default=SendUpdatesOption.ALL,
      description="Notification setting for participants",
  )


class UserScheduleRequest(BaseModel):
  request_text: str = Field(
      ...,
      min_length=5,
      max_length=5000,
      example=(
          "Schedule a team sync with john@example.com and sarah@company.com"
          " tomorrow at 3 PM UTC for 45 minutes to discuss project roadmap."
      ),
  )


class FunctionCallResponse(BaseModel):
  id: int
  cached: bool
  function_call: ScheduleCalendarEventFunction


class AuthUser(BaseModel):
    id: int
    email: EmailStr
    name: Optional[str] = None
    picture: Optional[str] = None


class TaskStatusResponse(BaseModel):
    task_id: str
    status: str
    result: Optional[dict] = None
    error: Optional[str] = None