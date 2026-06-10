from typing import Any, Dict
from datetime import datetime, date

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ServiceRequest, Master


async def create_service_request(session: AsyncSession, data: Dict[str, Any]) -> ServiceRequest:
    """
    Создаёт заявку на основе собранных данных из бота MAX.

    Обязательные поля в data:
      - user_id
      - chat_id
      - problem_description
      - location_type  ('workshop' / 'client_address')
    Остальное опционально.
    """

    required_fields = [
        "user_id",
        "chat_id",
        "problem_description",
        "location_type",
    ]
    missing = [f for f in required_fields if f not in data or data[f] is None]
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

    # --- расчёт master_seq per-мастер ---

    master_id = data.get("master_id")

    next_seq: int | None = None
    if master_id is not None:
        result = await session.execute(
            select(func.coalesce(func.max(ServiceRequest.master_seq), 0)).where(
                ServiceRequest.master_id == master_id
            )
        )
        current_max = result.scalar_one()
        next_seq = current_max + 1

    # --- создание заявки ---

    obj = ServiceRequest(
        status="new",
        source="max_bot",
        user_external_id=data["user_id"],
        chat_external_id=data["chat_id"],

        master_id=master_id,
        master_seq=next_seq,

        assigned_master_id=data.get("assigned_master_id"),  # 👈 добавлено

        client_id=data.get("client_id"),
        client_name=data.get("client_name"),
        client_phone=data.get("client_phone"),

        main_category=data["main_category", "Указать"],
        subtype=data["subtype", "Указать"],
        custom_device=data.get("custom_device", "Указать"),

        service_title=data.get("service_title"),
        problem_description=data["problem_description"],

        location_type=data["location_type"],
        address=data.get("address"),
        address_details=data.get("address_details"),

        date_iso=data.get("date_iso"),
        time_slot=data.get("time_slot"),
        datetime_from=data.get("datetime_from"),
        datetime_to=data.get("datetime_to"),

        total_amount=data.get("total_amount"),
        currency=data.get("currency", "RUB"),
        payment_status=data.get("payment_status", "unpaid"),
        paid_amount=data.get("paid_amount"),
        paid_at=data.get("paid_at"),

        yandex_url=data.get("yandex_url"),
        google_url=data.get("google_url"),
        meta=data.get("meta"),
    )

    session.add(obj)
    await session.commit()
    await session.refresh(obj)
    return obj