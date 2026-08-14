import json
from celery_app import celery_app
from database import CalendarEventDB, engine
from engine import get_calendar_engine
from sqlmodel import Session


@celery_app.task(bind=True)
def execute_calendar_schedule_task(self, request_text: str):
  engine_instance = get_calendar_engine()

  # 1. Extract function call structure via Outlines
  func_call = engine_instance.extract_calendar_function(request_text)

  # 2. Simulate dispatch to Google Calendar API (google-api-python-client)
  google_calendar_api_response = {
      "google_event_id": "gcal_evt_99887766",
      "html_link": (
          "https://www.google.com/calendar/event?eid=Z2NhbF9ldnRfOTk4ODc3NjY"
      ),
      "status": "confirmed",
      "summary": func_call.summary,
      "start": func_call.start.model_dump(),
      "end": func_call.end.model_dump(),
      "attendees": func_call.attendees,
  }

  # 3. Persist record to Database
  with Session(engine) as session:
    db_record = CalendarEventDB(
        request_text=request_text,
        summary=func_call.summary,
        start_time=func_call.start.date_time,
        end_time=func_call.end.date_time,
        attendees_json=json.dumps(func_call.attendees),
        status="confirmed",
        raw_function_call_json=func_call.model_dump_json(),
    )
    session.add(db_record)
    session.commit()

  return {
      "function_call": func_call.model_dump(),
      "calendar_api_status": google_calendar_api_response,
  }