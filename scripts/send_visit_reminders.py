import asyncio
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.db.models import (
    Master,
    Notification,
    ServiceRequest,
    WebPushSubscription,
)
from app.db.session import AsyncSessionLocal
from app.services.masters_notify import notify_master_request_created
from app.services.webpush_sender import send_webpush


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def build_push_payload(request: ServiceRequest | None) -> dict:
    """
    Формирует короткий текст для нативного Web Push.
    Полная карточка заявки уходит через второго MAX-бота.
    """
    if not request:
        return {
            "title": "⏰ Напоминание о визите",
            "body": "До запланированного события остался примерно 1 час",
            "data": {
                "type": "visit_reminder",
                "url": "/app/mobile-requests",
            },
        }

    display_number = (
        request.master_seq
        if request.master_seq is not None
        else request.id
    )

    parts = [f"Заявка №{display_number}"]

    if request.client_name:
        parts.append(request.client_name)

    if request.address:
        parts.append(f"📍 {request.address}")

    if request.time_slot:
        parts.append(f"⏰ {request.time_slot}")

    return {
        "title": "⏰ Выезд через 1 час",
        "body": " · ".join(parts),
        "data": {
            "type": "visit_reminder",
            "request_id": request.id,
            "url": f"/app/mobile-requests?request_id={request.id}",
        },
    }


async def process_visit_reminders() -> None:
    now = utcnow()

    async with AsyncSessionLocal() as session:
        stmt = (
            select(Notification)
            .options(
                selectinload(Notification.master),
                selectinload(Notification.request),
            )

            .where(
                Notification.channel == "webpush",
                Notification.type == "visit_reminder",
                Notification.sent_at.is_(None),
                Notification.remind_at <= now,
            )
        )

        result = await session.execute(stmt)
        notifications = result.scalars().unique().all()

        print(
            "[send_visit_reminders] "
            f"found {len(notifications)} notifications to send"
        )

        for notif in notifications:
            master: Master | None = notif.master
            request: ServiceRequest | None = notif.request

            if not master:
                print(
                    "[send_visit_reminders] "
                    f"notification {notif.id} has no master, skip"
                )
                continue

            if not request:
                print(
                    "[send_visit_reminders] "
                    f"notification {notif.id} has no request, skip"
                )
                continue

            # 1. Всегда пытаемся отправить полную карточку во второй MAX-бот.
            max_ok = False

            try:
                max_ok = await notify_master_request_created(
                    request.id,
                    is_reminder=True,
                )

                print(
                    "[send_visit_reminders] "
                    f"MAX reminder for notification {notif.id}: "
                    f"{'sent' if max_ok else 'failed'}"
                )

            except Exception as exc:
                print(
                    "[send_visit_reminders] "
                    f"MAX reminder error for notification {notif.id}: {exc}"
                )

            # 2. Отправляем Web Push на все подписанные устройства мастера.
            webpush_ok = False

            subs_stmt = select(WebPushSubscription).where(
                WebPushSubscription.master_id == master.id
            )
            subs_result = await session.execute(subs_stmt)
            subscriptions = subs_result.scalars().all()

            if not subscriptions:
                print(
                    "[send_visit_reminders] "
                    f"master {master.id} has no webpush subscriptions"
                )
            else:
                payload = build_push_payload(request)

                for sub in subscriptions:
                    try:
                        ok = send_webpush(sub, payload)

                        if ok:
                            webpush_ok = True
                        else:
                            print(
                                "[send_visit_reminders] "
                                f"failed to send push to subscription {sub.id}, "
                                f"master {master.id}"
                            )

                    except Exception as exc:
                        print(
                            "[send_visit_reminders] "
                            f"webpush error for subscription {sub.id}, "
                            f"master {master.id}: {exc}"
                        )

            # 3. Не даём cron слать дубли.
            # Считаем доставленным, если прошёл хотя бы один канал.
            if max_ok or webpush_ok:
                notif.sent_at = now

                print(
                    "[send_visit_reminders] "
                    f"notification {notif.id} marked as sent "
                    f"(max={max_ok}, webpush={webpush_ok})"
                )
            else:
                print(
                    "[send_visit_reminders] "
                    f"notification {notif.id} not sent via any channel; "
                    "will retry on the next cron run"
                )

        await session.commit()

    print("[send_visit_reminders] done")


def main() -> None:
    asyncio.run(process_visit_reminders())


if __name__ == "__main__":
    main()