# app/api/webpush.py
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db  # подставь свой путь к get_db
from app.db.models import WebPushSubscription, Master

# тут зависит от того, как ты получаешь текущего мастера
from app.api.deps import get_current_master  # условно, поправь под себя

router = APIRouter(prefix="/api/webpush", tags=["webpush"])


class PushSubscriptionKeys(BaseModel):
    p256dh: str
    auth: str


class PushSubscriptionPayload(BaseModel):
    endpoint: str
    keys: PushSubscriptionKeys
    user_agent: Optional[str] = None


@router.post("/subscribe")
def subscribe_webpush(
    payload: PushSubscriptionPayload,
    db: Session = Depends(get_db),
    current_master: Master = Depends(get_current_master),
):
    """
    Сохраняем web push подписку для мастера.
    Вызывается из PWA, когда мастер нажимает 'Включить уведомления'.
    """
    sub = (
        db.query(WebPushSubscription)
        .filter(WebPushSubscription.endpoint == payload.endpoint)
        .first()
    )

    if sub:
        # обновляем привязку и мета
        sub.master_id = current_master.id
        sub.p256dh = payload.keys.p256dh
        sub.auth = payload.keys.auth
        sub.user_agent = payload.user_agent
        sub.last_used_at = datetime.utcnow()
    else:
        sub = WebPushSubscription(
            master_id=current_master.id,
            endpoint=payload.endpoint,
            p256dh=payload.keys.p256dh,
            auth=payload.keys.auth,
            user_agent=payload.user_agent,
        )
        db.add(sub)

    db.commit()
    return {"status": "ok"}