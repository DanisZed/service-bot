# app/services/webpush_sender.py
import json
import logging
from typing import Dict

from pywebpush import webpush, WebPushException

from app.db.models import WebPushSubscription


logger = logging.getLogger(__name__)

# Лучше подтащить из настроек/ENV
VAPID_PRIVATE_KEY = os.getenv("VAPID_PRIVATE_KEY", "h7g4XjuXHw5ONf460p_tUHNsvOholUQ1Zm1suIlJLI0")
VAPID_CLAIMS = {
    "sub": "uralentrade@gmail.com",
}


def send_webpush(sub: WebPushSubscription, payload: Dict) -> bool:
    """
    Отправляет один web push по подписке.
    Возвращает True, если отправка прошла успешно.
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
        logger.warning("WebPush failed for %s: %s", sub.endpoint, e)
        # 404/410 = подписка протухла, её можно удалить
        if e.response is not None and e.response.status_code in (404, 410):
            return False
        return False