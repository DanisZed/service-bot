# scripts/send_visit_reminders.py
import asyncio
from datetime import datetime, timezone

from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.db.models import Notification, WebPushSubscription, ServiceRequest, Master
from app.services.webpush_sender import send_webpush


def utcnow():
    return datetime.now(timezone.utc)


async def process_visit_reminders():
    now = utcnow()

    async with AsyncSessionLocal() as session:
        # 1. Берём все уведомления, которые пора отправить
        stmt = (
            select(Notification)
            .where(
                Notification.channel == "webpush",
                Notification.type == "visit_reminder",
                Notification.sent_at.is_(None),
                Notification.remind_at <= now,
            )
        )

        result = await session.execute(stmt)
        notifications = result.scalars().unique().all()

        print(f"[send_visit_reminders] found {len(notifications)} notifications to send")

        for notif in notifications:
            master: Master = notif.master
            request: ServiceRequest = notif.request

            if not master:
                print(f"[send_visit_reminders] notification {notif.id} has no master, skip")
                continue

            # 2. Подписки мастера
            subs_stmt = select(WebPushSubscription).where(
                WebPushSubscription.master_id == master.id
            )
            subs_result = await session.execute(subs_stmt)
            subscriptions = subs_result.scalars().all()

            if not subscriptions:
                print(
                    f"[send_visit_reminders] master {master.id} has no webpush subscriptions"
                )
                continue

            # 3. Формируем payload
            title = "Напоминание о выезде"
            parts = []

            if request:
                parts.append(f"Заявка №{request.id}")
                if request.address:
                    parts.append(f"Адрес: {request.address}")
                if request.datetime_from and request.datetime_to:
                    parts.append(
                        f"Окно: {request.datetime_from} — {request.datetime_to}"
                    )
                elif request.date_iso and request.time_slot:
                    parts.append(
                        f"Дата: {request.date_iso}, слот: {request.time_slot}"
                    )
            else:
                parts.append("Напоминание о визите")

            body = " | ".join(parts)

            payload = {
                "title": title,
                "body": body,
                "url": "/app/mobile-requests",
            }

            any_ok = False

            for sub in subscriptions:
                ok = send_webpush(sub, payload)
                if ok:
                    any_ok = True
                else:
                    # Здесь при желании можно удалять мёртвые подписки (410)
                    print(
                        f"[send_visit_reminders] failed to send to sub {sub.id}, master {master.id}"
                    )

            if any_ok:
                notif.sent_at = now
                print(f"[send_visit_reminders] notification {notif.id} marked as sent")

        await session.commit()

    print("[send_visit_reminders] done")


def main():
    asyncio.run(process_visit_reminders())


if __name__ == "__main__":
    main()