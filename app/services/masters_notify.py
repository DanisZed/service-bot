from typing import List, Optional
from datetime import datetime, timedelta

from app.db.session import AsyncSessionLocal
from app.db.models import ServiceRequest, Master
from max_client_second_bot import MaxClientSecondBot


def _build_yandex_url(address: Optional[str]) -> Optional[str]:
    if not address or address == "Мастерская":
        return None
    return f"https://yandex.ru/navi?text={address.replace(' ', '+')}"


def _build_google_calendar_url(
    order_no: Optional[int],
    date_iso: Optional[str],
    time_slot: Optional[str],
    address: Optional[str],
    address_details: Optional[str],
    comment: Optional[str],
    phone: Optional[str],
    tz: str = "Europe/Moscow",
) -> str:
    order_part = f"Заявка №{order_no}" if order_no is not None else "Заявка"
    text_param = order_part.replace(" ", "+")
    address_param = (address or "").replace(" ", "+")
    details_str = comment or ""
    if address_details:
        details_str += f" ({address_details})"
    if phone:
        if details_str:
            details_str += ". "
        details_str += f"Телефон: +{phone}"
    details_param = details_str.replace(" ", "+")

    if date_iso:
        try:
            d = datetime.strptime(date_iso, "%Y-%m-%d")
        except ValueError:
            d = datetime.now()
    else:
        d = datetime.now()

    if time_slot and "-" in time_slot:
        start_str, end_str = time_slot.split("-", 1)
        try:
            start_dt = datetime.combine(d.date(), datetime.strptime(start_str, "%H:%M").time())
            end_dt = datetime.combine(d.date(), datetime.strptime(end_str, "%H:%M").time())
        except ValueError:
            start_dt = d
            end_dt = d + timedelta(hours=1)
    else:
        start_dt = datetime.combine(d.date(), datetime.strptime("10:00", "%H:%M").time())
        end_dt = start_dt + timedelta(hours=1)

    dates_param = f"{start_dt.strftime('%Y%m%dT%H%M00')}/{end_dt.strftime('%Y%m%dT%H%M00')}"

    base = "https://www.google.com/calendar/render"
    parts = [
        "action=TEMPLATE",
        f"text={text_param}",
        f"dates={dates_param}",
        f"details={details_param}",
        f"location={address_param}",
        f"ctz={tz}",
    ]
    return base + "?" + "&".join(parts)


async def notify_master_request_created(request_id: int) -> None:
    """
    Уведомляет мастера о созданной заявке через второго бота.
    Требования:
      - ServiceRequest.master_id заполнен,
      - Master.max_user_id — user_id мастера, которого знает второй бот.
    """
    async with AsyncSessionLocal() as session:
        req = await session.get(ServiceRequest, request_id)
        if not req or not req.master_id:
            return

        master = await session.get(Master, req.master_id)
        if not master or not master.max_user_id:
            return

        lines: List[str] = [f"📝 Заявка № {req.id}"]

        if req.service_title or req.subtype:
            lines.append(f"🔧 Услуга: {req.service_title or req.subtype}")

        if req.problem_description:
            lines.append(f"📄 Описание: {req.problem_description}")

        if req.address == "Мастерская":
            lines.append("🏭 Место выполнения: мастерская")
        elif req.address:
            lines.append(f"📍 Адрес: {req.address}")
        else:
            lines.append("📍 Адрес: не указан")

        if req.address_details:
            lines.append(f"📌 Уточнение по адресу: {req.address_details}")

        date_iso_str: Optional[str] = None
        if isinstance(req.date_iso, datetime):
            lines.append(f"📅 Дата: {req.date_iso.strftime('%d.%m.%Y')}")
            date_iso_str = req.date_iso.date().isoformat()
        else:
            date_iso_str = req.date_iso
            if req.date_iso:
                lines.append(f"📅 Дата: {req.date_iso}")

        if req.time_slot:
            lines.append(f"⏰ Время/слот: {req.time_slot}")

        if req.client_name:
            lines.append(f"🙋‍♂️ Клиент: {req.client_name}")
        if req.client_phone:
            lines.append(f"📞 Телефон: {req.client_phone}")

        text = "\n".join(lines)

        yandex_url = _build_yandex_url(req.address)
        google_url = _build_google_calendar_url(
            order_no=req.id,
            date_iso=date_iso_str,
            time_slot=req.time_slot,
            address=req.address,
            address_details=req.address_details,
            comment=req.problem_description,
            phone=req.client_phone,
        )

        buttons_rows: List[List[dict]] = []
        if yandex_url:
            buttons_rows.append(
                [
                    {
                        "type": "link",
                        "text": "Проложить маршрут (Яндекс)",
                        "url": yandex_url,
                    }
                ]
            )

        if google_url:
            buttons_rows.append(
                [
                    {
                        "type": "link",
                        "text": "Добавить в Google Календарь",
                        "url": google_url,
                    }
                ]
            )

        attachments = None
        if buttons_rows:
            attachments = [
                {
                    "type": "inline_keyboard",
                    "payload": {"buttons": buttons_rows},
                }
            ]

        client = MaxClientSecondBot()
        try:
            await client.send_text_to_user(
                user_id=master.max_user_id,
                text=text,
                attachments=attachments,
            )
        finally:
            await client.close()