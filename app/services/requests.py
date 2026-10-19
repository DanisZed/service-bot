# app/services/requests.py
from datetime import datetime, time, timedelta
from typing import Any, Dict, Optional, Tuple

from sqlalchemy import func, select
from app.db.models import ServiceRequest
from app.services.notifications import schedule_visit_reminders


def parse_visit_datetimes(
    date_iso: Any,
    time_slot: Any,
) -> Tuple[Optional[datetime], Optional[datetime]]:
    """
    Преобразует:
        date_iso = 2026-10-17
        time_slot = "11:00-12:00"

    В:
        datetime_from = 2026-10-17 11:00:00
        datetime_to   = 2026-10-17 12:00:00

    Если дату или слот распознать нельзя — возвращает (None, None).
    """
    if not date_iso or not time_slot:
        return None, None

    if isinstance(date_iso, str):
        try:
            visit_date = datetime.strptime(date_iso, "%Y-%m-%d").date()
        except ValueError:
            return None, None
    elif hasattr(date_iso, "year") and hasattr(date_iso, "month"):
        visit_date = date_iso
    else:
        return None, None

    if not isinstance(time_slot, str):
        return None, None

    normalized_slot = (
        time_slot.strip()
        .replace("–", "-")
        .replace("—", "-")
        .replace(" ", "")
    )

    try:
        start_text, end_text = normalized_slot.split("-", maxsplit=1)
        start_time = datetime.strptime(start_text, "%H:%M").time()
        end_time = datetime.strptime(end_text, "%H:%M").time()
    except ValueError:
        return None, None

    datetime_from = datetime.combine(visit_date, start_time)
    datetime_to = datetime.combine(visit_date, end_time)

    # На случай ночного слота, например 23:00-01:00.
    if datetime_to <= datetime_from:
        datetime_to += timedelta(days=1)

    return datetime_from, datetime_to


async def create_service_request(
    session: AsyncSession,
    data: Dict[str, Any],
) -> ServiceRequest:
    """
    Создаёт заявку из MAX-бота или веб-интерфейса.

    Если точные datetime_from/datetime_to не переданы, они формируются
    из date_iso и time_slot формата «11:00-12:00».
    """
    required_fields = [
        "user_id",
        "chat_id",
        "problem_description",
        "location_type",
    ]
    missing = [
        field
        for field in required_fields
        if field not in data or data[field] is None
    ]
    if missing:
        raise ValueError(
            f"Missing required fields for ServiceRequest: {', '.join(missing)}"
        )

    raw_date_iso = data.get("date_iso")
    if isinstance(raw_date_iso, str):
        try:
            data["date_iso"] = datetime.strptime(raw_date_iso, "%Y-%m-%d").date()
        except ValueError:
            data["date_iso"] = None

    # Если бот/фронт явно передал точное время — используем его.
    # Иначе собираем время из date_iso + time_slot.
    datetime_from = data.get("datetime_from")
    datetime_to = data.get("datetime_to")

    if datetime_from is None:
        parsed_from, parsed_to = parse_visit_datetimes(
            data.get("date_iso"),
            data.get("time_slot"),
        )
        datetime_from = parsed_from
        datetime_to = datetime_to or parsed_to

    master_id = data.get("master_id")

    next_seq: Optional[int] = None
    if master_id is not None:
        result = await session.execute(
            select(
                func.coalesce(
                    func.max(ServiceRequest.master_seq),
                    0,
                )
            ).where(ServiceRequest.master_id == master_id)
        )
        next_seq = result.scalar_one() + 1

    obj = ServiceRequest(
        status="new",
        source=data.get("source", "max_bot"),
        user_external_id=data["user_id"],
        chat_external_id=data["chat_id"],
        master_id=master_id,
        master_seq=next_seq,
        assigned_master_id=data.get("assigned_master_id"),
        client_id=data.get("client_id"),
        client_name=data.get("client_name"),
        client_phone=data.get("client_phone"),
        main_category=data.get("main_category", "Указать"),
        subtype=data.get("subtype", "Указать"),
        custom_device=data.get("custom_device", "Указать"),
        service_title=data.get("service_title"),
        problem_description=data["problem_description"],
        repair_description=data.get("repair_description", ""),
        warranty_period=data.get("warranty_period"),
        location_type=data["location_type"],
        address=data.get("address"),
        address_details=data.get("address_details"),
        date_iso=data.get("date_iso"),
        time_slot=data.get("time_slot"),
        datetime_from=datetime_from,
        datetime_to=datetime_to,
        total_amount=data.get("total_amount"),
        parts_cost=data.get("parts_cost"),
        currency=data.get("currency", "RUB"),
        payment_status=data.get("payment_status", "unpaid"),
        paid_amount=data.get("paid_amount"),
        paid_at=data.get("paid_at"),
        yandex_url=data.get("yandex_url"),
        google_url=data.get("google_url"),
        meta=data.get("meta"),
    )

    session.add(obj)

    # flush присваивает obj.id, но не делает отдельный commit.
    await session.flush()

    await schedule_visit_reminders(session, obj)

    await session.commit()
    await session.refresh(obj)

    return obj