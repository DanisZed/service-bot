# app/services/notifications.py
from datetime import timedelta

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Notification, ServiceRequest


async def schedule_visit_reminders(
    db: AsyncSession,
    request: ServiceRequest,
) -> None:
    """
    Пересоздаёт напоминания за один час до выезда.

    Получатели:
    - владелец заявки: request.master_id;
    - назначенный исполнитель: request.assigned_master_id.

    Если это один и тот же мастер — создаётся только одно напоминание.
    """
    # Без точного времени выезда напоминание запланировать нельзя.
    if not request.datetime_from:
        return

    # Не напоминаем о завершённых/отменённых заявках.
    if request.status in {"done", "canceled"}:
        return

    remind_at = request.datetime_from - timedelta(hours=1)

    # Удаляем только старые, ещё не отправленные напоминания этой заявки.
    # Отправленные остаются как история.
    await db.execute(
        delete(Notification).where(
            Notification.request_id == request.id,
            Notification.type == "visit_reminder",
            Notification.channel == "webpush",
            Notification.sent_at.is_(None),
        )
    )

    # Уведомляем владельца и исполнителя; set автоматически убирает дубли.
    recipient_ids = {
        master_id
        for master_id in (
            request.master_id,
            request.assigned_master_id,
        )
        if master_id is not None
    }

    for master_id in recipient_ids:
        db.add(
            Notification(
                master_id=master_id,
                request_id=request.id,
                remind_at=remind_at,
                type="visit_reminder",
                channel="webpush",
            )
        )