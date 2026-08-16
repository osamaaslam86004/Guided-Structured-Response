import json
from celery_app import celery_app
from database import CalendarEventDB, engine
from engine import get_calendar_engine
from sqlmodel import Session
from gcloud_service import get_gcal_service


@celery_app.task(bind=True)
def execute_calendar_schedule_task(self, request_text: str):
  engine_instance = get_calendar_engine()

  # 1. Extract function call structure via Outlines
  func_call = engine_instance.extract_calendar_function(request_text)

  # 2. Call Google Calendar API to create event and generate Google Meet Link
  gcal_service = get_gcal_service()
  gcal_response = gcal_service.create_event_with_meet(func_call)

  meeting_link = gcal_response.get("meeting_link")

  # 3. Persist record to Database
  with Session(engine) as session:
    db_record = CalendarEventDB(
        request_text=request_text,
        summary=func_call.summary,
        start_time=func_call.start.date_time,
        end_time=func_call.end.date_time,
        attendees_json=json.dumps(func_call.attendees),
        meeting_link=meeting_link,
        status=gcal_response.get("status", "scheduled"),
        raw_function_call_json=func_call.model_dump_json(),
    )
    session.add(db_record)
    session.commit()

    return {
        "function_call": func_call.model_dump(),
        "google_calendar_event": gcal_response,
        "meeting_link": meeting_link,
    }