# app/services/webpush_sender.py
import os
import json
from pywebpush import webpush, WebPushException
from app.db.models import WebPushSubscription

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
        # ВРЕМЕННО логируем, чтобы увидеть, что отвечает push-сервис
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