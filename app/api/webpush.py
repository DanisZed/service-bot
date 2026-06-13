# app/api/webpush.py
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_async_session  # ИСПОЛЬЗУЕМ async dependency[web:424]
from app.db.models import WebPushSubscription, Master
from app.api.deps import get_current_master  # как у тебя уже сделано в других роутерах

router = APIRouter(prefix="/api/webpush", tags=["webpush"])


class PushSubscriptionKeys(BaseModel):
    p256dh: str
    auth: str


class PushSubscriptionPayload(BaseModel):
    endpoint: str
    keys: PushSubscriptionKeys
    user_agent: Optional[str] = None


@router.post("/subscribe")
async def subscribe_webpush(
    payload: PushSubscriptionPayload,
    session: AsyncSession = Depends(get_async_session),
    current_master: Master = Depends(get_current_master),
):
    """
    Сохраняем Web Push подписку для мастера.
    Вызывается из PWA, когда мастер включает уведомления.
    """

    # Ищем подписку по endpoint (он уникален для браузера/устройства)
    result = await session.execute(
        select(WebPushSubscription).where(
            WebPushSubscription.endpoint == payload.endpoint
        )
    )
    sub: WebPushSubscription | None = result.scalar_one_or_none()

    now = datetime.utcnow()

    if sub:
        sub.master_id = current_master.id
        sub.p256dh = payload.keys.p256dh
        sub.auth = payload.keys.auth
        sub.user_agent = payload.user_agent
        sub.last_used_at = now
    else:
        sub = WebPushSubscription(
            master_id=current_master.id,
            endpoint=payload.endpoint,
            p256dh=payload.keys.p256dh,
            auth=payload.keys.auth,
            user_agent=payload.user_agent,
            created_at=now,
            last_used_at=now,
        )
        session.add(sub)

    await session.commit()
    return {"status": "ok"}