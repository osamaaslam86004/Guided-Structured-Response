import json
from google_auth_oauthlib.flow import InstalledAppFlow
import redis
from sqlmodel import Session, select

from database import OAuthTokenDB, engine  # Citing database [source: 10]

SCOPES = ["https://www.googleapis.com/auth/calendar"]
CLIENT_SECRETS_FILE = "client_secret.json"
USER_EMAIL = "primary_user"


def seed_oauth_credentials():
  # 1. Trigger interactive OAuth login in browser
  flow = InstalledAppFlow.from_client_secrets_file(
      CLIENT_SECRETS_FILE, SCOPES
  )
  creds = flow.run_local_server(port=8080)

  with open(CLIENT_SECRETS_FILE) as f:
    client_config = json.load(f)
    client_data = client_config.get("installed") or client_config.get("web")

  expiry_str = creds.expiry.isoformat() if creds.expiry else None

  # 2. Store token in SQLite Database
  with Session(engine) as session:
    existing = session.exec(
        select(OAuthTokenDB).where(OAuthTokenDB.user_email == USER_EMAIL)
    ).first()
    if existing:
      session.delete(existing)
      session.commit()

    db_token = OAuthTokenDB(
        user_email=USER_EMAIL,
        access_token=creds.token,
        refresh_token=creds.refresh_token,
        client_id=client_data["client_id"],
        client_secret=client_data["client_secret"],
        scopes_json=json.dumps(SCOPES),
        expiry=expiry_str,
    )
    session.add(db_token)
    session.commit()

  # 3. Cache token in Redis (db=1)
  redis_client = redis.Redis(
      host="localhost", port=6379, db=1, decode_responses=True
  )
  token_dict = {
      "token": creds.token,
      "refresh_token": creds.refresh_token,
      "token_uri": "https://oauth2.googleapis.com/token",
      "client_id": client_data["client_id"],
      "client_secret": client_data["client_secret"],
      "scopes": SCOPES,
      "expiry": expiry_str,
  }
  redis_client.set(
      f"google_oauth_token:{USER_EMAIL}", json.dumps(token_dict), 3600
  )

  print("Successfully saved OAuth token to SQLite and Redis!")


if __name__ == "__main__":
  seed_oauth_credentials()