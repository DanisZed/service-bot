# app/services/webpush_sender.py
import json
import os
from pathlib import Path

from dotenv import load_dotenv
from pywebpush import WebPushException, webpush

from app.db.models import WebPushSubscription


PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")

VAPID_PRIVATE_KEY = os.getenv("VAPID_PRIVATE_KEY", "")
VAPID_SUBJECT = os.getenv("VAPID_SUBJECT", "mailto:you@example.com")

VAPID_CLAIMS = {
    "sub": VAPID_SUBJECT,
}


def send_webpush(sub: WebPushSubscription, payload: dict) -> bool:
    try:
        webpush(
            subscription_info={
                "endpoint": sub.endpoint,
                "keys": {
                    "p256dh": sub.p256dh,
                    "auth": sub.auth,
                },
            },
            data=json.dumps(payload, ensure_ascii=False),
            vapid_private_key=VAPID_PRIVATE_KEY,
            vapid_claims=VAPID_CLAIMS,
        )
        return True
    except WebPushException as e:
        status = getattr(e.response, "status_code", None)
        body = None

        try:
            if e.response is not None:
                body = e.response.content
        except Exception:
            pass

        print("WebPushException status:", status)
        print("WebPushException body:", body)
        print("Endpoint:", sub.endpoint)
        return False