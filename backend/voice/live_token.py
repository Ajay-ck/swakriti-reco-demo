import os
from google import genai
import datetime


def create_live_token():
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("GOOGLE_API_KEY is not set — check your backend .env file")

    client = genai.Client(api_key=api_key, http_options={'api_version': 'v1alpha'})
    now = datetime.datetime.now(datetime.timezone.utc)
    token = client.auth_tokens.create(config={
        'uses': 1,
        'expire_time': now + datetime.timedelta(minutes=30),
        'new_session_expire_time': now + datetime.timedelta(minutes=1),
        'live_connect_constraints': {
            'model': 'gemini-3.1-flash-live-preview',
            'config': {'response_modalities': ['AUDIO']}
        }
    })
    return token.name