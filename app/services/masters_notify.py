import logging
import os
from datetime import datetime, timedelta
from typing import List, Optional

from app.db.models import Master, ServiceRequest
from app.db.session import AsyncSessionLocal
from max_client import MaxClient


logger = logging.getLogger(__name__)

MAX_ORDER_BOT_TOKEN = os.getenv("MAX_ORDER_BOT_TOKEN")


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
) -> str:
    title = f"Заявка №{order_no}" if order_no is not None else "Заявка"
    text_param = title.replace(" ", "+")
    address_param = (address or "").replace(" ", "+")

    details_str = comment or ""

    if address_details:
        details_str += f" ({address_details})"

    if phone:
        raw = "".join(ch for ch in phone if ch.isdigit())

        if raw.startswith("7") and len(raw) == 11:
            phone_display = "8" + raw[1:]
        elif raw.startswith("8") and len(raw) == 11:
            phone_display = raw
        elif len(raw) == 10 and raw.startswith("9"):
            phone_display = "8" + raw
        else:
            phone_display = raw

        if details_str:
            details_str += ". "

        details_str += f"Телефон: {phone_display}"

    details_param = details_str.replace(" ", "+")

    if date_iso:
        try:
            date_value = datetime.strptime(date_iso, "%Y-%m-%d")
        except ValueError:
            date_value = datetime.now()
    else:
        date_value = datetime.now()

    if time_slot and "-" in time_slot:
        start_str, end_str = time_slot.split("-", 1)

        try:
            start_dt = datetime.combine(
                date_value.date(),
                datetime.strptime(start_str.strip(), "%H:%M").time(),
            )
            end_dt = datetime.combine(
                date_value.date(),
                datetime.strptime(end_str.strip(), "%H:%M").time(),
            )
        except ValueError:
            start_dt = date_value
            end_dt = date_value + timedelta(hours=1)
    else:
        start_dt = datetime.combine(
            date_value.date(),
            datetime.strptime("10:00", "%H:%M").time(),
        )
        end_dt = start_dt + timedelta(hours=1)

    dates_param = (
        f"{start_dt.strftime('%Y%m%dT%H%M00')}/"
        f"{end_dt.strftime('%Y%m%dT%H%M00')}"
    )

    base = "https://www.google.com/calendar/render"

    parts = [
        "action=TEMPLATE",
        f"text={text_param}",
        f"dates={dates_param}",
        f"details={details_param}",
        f"location={address_param}",
    ]

    return base + "?" + "&".join(parts)


def _request_date_iso(req: ServiceRequest) -> Optional[str]:
    if isinstance(req.date_iso, datetime):
        return req.date_iso.date().isoformat()

    if hasattr(req.date_iso, "isoformat"):
        return req.date_iso.isoformat()

    return str(req.date_iso) if req.date_iso else None


async def notify_master_request_created(
    request_id: int,
    *,
    is_reminder: bool = False,
) -> bool:
    """
    Отправляет карточку назначенному мастеру через второго MAX-бота.

    is_reminder=False: обычная новая заявка.
    is_reminder=True: напоминание о выезде примерно через один час.
    """
    logger.info(
        "notify_master_request_created: request_id=%s, is_reminder=%s",
        request_id,
        is_reminder,
    )

    if not MAX_ORDER_BOT_TOKEN:
        logger.error("MAX_ORDER_BOT_TOKEN is not configured")
        return False

    async with AsyncSessionLocal() as session:
        req = await session.get(ServiceRequest, request_id)

        if not req:
            logger.warning(
                "notify_master_request_created: request %s not found",
                request_id,
            )
            return False

        target_master_id = req.assigned_master_id or req.master_id

        if not target_master_id:
            logger.warning(
                "notify_master_request_created: no target master for request %s",
                request_id,
            )
            return False

        master = await session.get(Master, target_master_id)

        if not master or not master.max_user_id:
            logger.warning(
                "notify_master_request_created: master %s not found "
                "or has no max_user_id",
                target_master_id,
            )
            return False

        display_number = (
            req.master_seq
            if req.master_seq is not None
            else req.id
        )

        lines: List[str] = []

        if is_reminder:
            lines.extend(
                [
                    "⏰ НАПОМИНАНИЕ",
                    "До выезда по заявке остался примерно 1 час.",
                    "",
                ]
            )

        lines.append(f"📝 ЗАЯВКА № {display_number}")

        if req.problem_description:
            lines.append(f"📄 Причина обращения: {req.problem_description}")

        if req.address == "Мастерская":
            lines.append("🏭 Мастерская")
        elif req.address:
            lines.append(f"📍 Адрес: {req.address}")
        else:
            lines.append("📍 Адрес: не указан")

        if req.address_details:
            lines.append(f"❗️ Уточнение по адресу: {req.address_details}")

        date_iso_str = _request_date_iso(req)

        if isinstance(req.date_iso, datetime):
            lines.append(f"📅 Дата: {req.date_iso.strftime('%d.%m.%Y')}")
        elif hasattr(req.date_iso, "strftime"):
            lines.append(f"📅 Дата: {req.date_iso.strftime('%d.%m.%Y')}")
        elif req.date_iso:
            lines.append(f"📅 Дата: {req.date_iso}")

        if req.time_slot:
            lines.append(f"⏰ Время: {req.time_slot}")

        if req.client_name:
            lines.append(f"🙋‍♂️ Клиент: {req.client_name}")

        if req.client_phone:
            lines.append(f"📞 Телефон: {req.client_phone}")

        text = "\n".join(lines)

        yandex_url = _build_yandex_url(req.address)

        google_url = _build_google_calendar_url(
            order_no=display_number,
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
                        "text": "🚘 Открыть Яндекс.Навигатор",
                        "url": yandex_url,
                    }
                ]
            )

        if google_url:
            buttons_rows.append(
                [
                    {
                        "type": "link",
                        "text": "📅 Добавить в Google Календарь",
                        "url": google_url,
                    }
                ]
            )

        buttons_rows.append(
            [
                {
                    "type": "callback",
                    "text": "🖨️ Гарантийный талон",
                    "payload": f"sticker:{req.id}",
                }
            ]
        )

        attachments = (
            [
                {
                    "type": "inline_keyboard",
                    "payload": {"buttons": buttons_rows},
                }
            ]
            if buttons_rows
            else None
        )

        logger.info(
            "notify_master_request_created: sending to master=%s, request=%s",
            master.max_user_id,
            req.id,
        )

        client = MaxClient(token=MAX_ORDER_BOT_TOKEN)

        try:
            response = await client.send_text_to_user(
                user_id=master.max_user_id,
                text=text,
                attachments=attachments,
            )

            logger.info(
                "notify_master_request_created: request=%s response=%s",
                request_id,
                response,
            )

            return True

        except Exception:
            logger.exception(
                "notify_master_request_created: send failed for request=%s",
                request_id,
            )
            return False

        finally:
            await client.close()