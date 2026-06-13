# app/services/notifications.py
from datetime import timedelta
from sqlalchemy.orm import Session

from app.db.models import ServiceRequest, Notification

def schedule_visit_reminder(db: Session, request: ServiceRequest) -> None:
    """
    Создаёт или обновляет напоминание 'за час до визита' для заявки.
    """
    if not request.datetime_from:
        return
    if not request.assigned_master_id:
        return

    remind_at = request.datetime_from - timedelta(hours=1)

    # чистим старое напоминание для этой заявки (если было)
    db.query(Notification).filter(
        Notification.request_id == request.id,
        Notification.type == "visit_reminder",
        Notification.channel == "webpush",
    ).delete()

    notif = Notification(
        master_id=request.assigned_master_id,
        request_id=request.id,
        remind_at=remind_at,
        type="visit_reminder",
        channel="webpush",
    )
    db.add(notif)