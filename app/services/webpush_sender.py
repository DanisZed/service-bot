# app/services/webpush_sender.py
import os
import json

from pywebpush import webpush, WebPushException

from app.db.models import WebPushSubscription

VAPID_PRIVATE_KEY = os.getenv("VAPID_PRIVATE_KEY", "")
VAPID_PUBLIC_KEY = os.getenv("VAPID_PUBLIC_KEY", "")
VAPID_SUBJECT = os.getenv("VAPID_SUBJECT", "")

VAPID_CLAIMS = {
    "sub": VAPID_SUBJECT,
}


def send_webpush(sub: WebPushSubscription, payload: dict) -> bool:
    """
    Отправляет один web push по подписке.
    Возвращает True, если отправка прошла без ошибок, False если подписка мёртвая/ошибка.
    """
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
        # 404/410 — подписка устарела, её надо удалить
        if e.response is not None and e.response.status_code in (404, 410):
            return False
        # остальные ошибки тоже считаем неуспешной отправкой
        return False