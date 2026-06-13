# app/scripts/send_visit_reminders.py
import json
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import joinedload

from app.db.session import async_session_maker  # или свой фабричный метод
from app.db.models import Notification, WebPushSubscription, ServiceRequest
from app.services.webpush_sender import send_webpush
async def process_visit_reminders():
    async with async_session_maker() as session:
        now = datetime.now(timezone.utc)

        # Подтягиваем связанные заявки сразу (joinedload)
        result = await session.execute(
            select(Notification)
            .options(joinedload(Notification.request))
            .where(Notification.type == "visit_reminder")
            .where(Notification.channel == "webpush")
            .where(Notification.sent_at.is_(None))
            .where(Notification.remind_at <= now)
        )
        notifications: list[Notification] = list(result.scalars())

        for notif in notifications:
            request: ServiceRequest = notif.request

            subs_result = await session.execute(
                select(WebPushSubscription).where(
                    WebPushSubscription.master_id == notif.master_id
                )
            )
            subs: list[WebPushSubscription] = list(subs_result.scalars())

            if not subs:
                # подписок нет — просто помечаем как отправленное, чтобы не висело
                notif.sent_at = now
                continue

            title = f"Через час заявка №{request.master_seq or request.id}"
            parts = []
            if request.address:
                parts.append(request.address)
            if request.subtype:
                parts.append(request.subtype)
            if request.client_name:
                parts.append(request.client_name)
            body = " — ".join(parts) or "Напоминание о визите"

            payload = {
                "title": title,
                "body": body,
                "request_id": int(request.id),
                "master_seq": request.master_seq,
                "url": f"/app/mobile-requests?request_id={int(request.id)}",
            }

            dead_sub_ids: list[int] = []

            for sub in subs:
                ok = send_webpush(sub, payload)
                if not ok:
                    dead_sub_ids.append(sub.id)

            # помечаем уведомление как отправленное
            notif.sent_at = now

            # можно сразу удалить протухшие подписки
            if dead_sub_ids:
                await session.execute(
                    WebPushSubscription.__table__.delete().where(
                        WebPushSubscription.id.in_(dead_sub_ids)
                    )
                )

        await session.commit()

        # app/scripts/send_visit_reminders.py (продолжение)
import asyncio

if __name__ == "__main__":
    asyncio.run(process_visit_reminders())