# app/services/masters_notify.py
import os
from typing import List, Optional
from datetime import datetime, timedelta

import logging

from app.db.session import AsyncSessionLocal
from app.db.models import ServiceRequest, Master
from max_client import MaxClient

logger = logging.getLogger(__name__)

MAX_ORDER_BOT_TOKEN = os.getenv("MAX_ORDER_BOT_TOKEN")

# Словарь (можно вынести в начало файла или импортировать)
SUBTYPE_NAMES = {
    # Крупная бытовая техника
    "washing_machine": "Стиральные машины",
    "dishwasher": "Посудомоечные машины",
    "dryer": "Сушильные машины",
    "water_heater": "Водонагреватели",
    "fridge": "Холодильники и морозильники",
    # Кухонная техника
    "oven": "Электрические духовки",
    "cooking_surface": "Электрические плиты",
    "microwave": "Микроволновые печи",
    # Электроприборы и инструменты
    "welding": "Сварочные аппараты",
    "stabilizer_ups": "Стабилизаторы и бесперебойники",
    "power_tools": "Электроинструмент",
    # Климатическая техника
    "heater": "Обогреватели",
    "air_conditioner": "Кондиционеры",
    # Мелкая кухонная техника
    "kitchen_iron_steamer": "Отпариватели и утюги",
    "kitchen_mixer_blender": "Миксеры и блендеры",
    "meat_grinder_processor": "Мясорубки и комбайны",
    "baker_multicooker": "Хлебопечи и мультиварки",
    # Мелкая бытовая техника
    "home_iron_steamer": "Парогенераторы и утюги",
    "vacuum": "Пылесосы",
    "hair_care": "Фены и стайлеры",
    "humidifier": "Увлажнители",
}


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
    Уведомляет назначенного мастера (или владельца, если назначенного нет) о заявке.
    """
    logger.info(f"notify_master_request_created: request_id={request_id}")

    async with AsyncSessionLocal() as session:
        req = await session.get(ServiceRequest, request_id)
        if not req:
            logger.warning(f"notify_master_request_created: request {request_id} not found")
            return

        # Кому отправлять: назначенный мастер или владелец
        target_master_id = req.assigned_master_id or req.master_id
        if not target_master_id:
            logger.warning(f"notify_master_request_created: no target master for request {request_id}")
            return

        master = await session.get(Master, target_master_id)
        if not master or not master.max_user_id:
            logger.warning(f"notify_master_request_created: master {target_master_id} not found or no max_user_id")
            return

        # Формирование текста сообщения (без изменений)
        lines: List[str] = [f"📝 ЗАЯВКА № {req.id}\n"]

        if req.service_title or req.subtype:            
            lines.append(f"🔧 Вид техники: {SUBTYPE_NAMES.get(req.subtype, req.subtype)}")

        if req.problem_description:
            lines.append(f"📄 Описание: {req.problem_description}")

        if req.address == "Мастерская":
            lines.append("🏭 Мастерская")
        elif req.address:
            lines.append(f"📍 Адрес: {req.address}")
        else:
            lines.append("📍 Адрес: не указан")

        if req.address_details:
            lines.append(f"❗️ Уточнение по адресу: {req.address_details}")

        date_iso_str: Optional[str] = None
        if isinstance(req.date_iso, datetime):
            lines.append(f"📅 Дата: {req.date_iso.strftime('%d.%m.%Y')}")
            date_iso_str = req.date_iso.date().isoformat()
        elif hasattr(req.date_iso, "isoformat"):
            lines.append(f"📅 Дата: {req.date_iso.strftime('%d.%m.%Y')}")
            date_iso_str = req.date_iso.isoformat()
        else:
            date_iso_str = str(req.date_iso) if req.date_iso else None
            if req.date_iso:
                lines.append(f"📅 Дата: {date_iso_str}")

        if req.time_slot:
            lines.append(f"⏰ Время: {req.time_slot}")

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
            buttons_rows.append([{"type": "link", "text": "Проложить маршрут (Яндекс)", "url": yandex_url}])
        if google_url:
            buttons_rows.append([{"type": "link", "text": "Добавить в Google Календарь", "url": google_url}])

        attachments = None
        if buttons_rows:
            attachments = [{"type": "inline_keyboard", "payload": {"buttons": buttons_rows}}]

        logger.info(f"notify_master_request_created: sending to master {master.max_user_id}")

        client = MaxClient(token=MAX_ORDER_BOT_TOKEN)
        try:
            resp = await client.send_text_to_user(user_id=master.max_user_id, text=text, attachments=attachments)
            logger.info(f"notify_master_request_created: response={resp}")
        finally:
            await client.close()