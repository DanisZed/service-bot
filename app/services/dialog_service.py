"""Сервис диалогов для Max бота (Диспетчер)"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, Optional, List, Tuple
import os

from max_client import MaxClient

from app.db.session import AsyncSessionLocal
from app.services.requests import create_service_request
from app.services.masters_notify import notify_master_request_created
from app.services.registration_service import registration_service

from app.db.models import Master, ServiceRequest

from sqlalchemy import select

import jwt
from app.services.masters_notify import _build_google_calendar_url


class DialogState:
    ADDRESS_MODE = "address_mode"
    ADDRESS = "address"
    ADDRESS_DETAILS = "address_details"
    DESCRIPTION = "description"
    SLOT = "slot"
    SLOT_TIME = "slot_time"
    NAME = "name"
    PHONE = "phone"
    CONFIRMED = "confirmed"


@dataclass
class DialogContext:
    state: str = DialogState.ADDRESS_MODE

    chat_id: Optional[int] = None
    address: Optional[str] = None
    address_details: Optional[str] = None
    description: Optional[str] = None
    date_iso: Optional[str] = None
    date: Optional[str] = None
    slot: Optional[str] = None
    name: Optional[str] = None
    phone: Optional[str] = None
    request_id: Optional[int] = None


WEEKDAY_SHORT_RU = ["пн", "вт", "ср", "чт", "пт", "сб", "вс"]
WEEKDAY_FULL_RU = [
    "Понедельник",
    "Вторник",
    "Среда",
    "Четверг",
    "Пятница",
    "Суббота",
    "Воскресенье",
]

TIME_SLOTS = [
    ("09:00", "10:00"),
    ("10:00", "11:00"),
    ("11:00", "12:00"),
    ("12:00", "13:00"),
    ("13:00", "14:00"),
    ("14:00", "15:00"),
    ("15:00", "16:00"),
    ("16:00", "17:00"),
    ("17:00", "18:00"),
]


def _get_panel_login_url(self, user_id: int) -> str:
    """Генерирует ссылку для авторизации в панели по MAX user_id."""
    payload = {
        "sub": str(user_id),
        "exp": datetime.utcnow() + timedelta(hours=24),
        "type": "max_auto_login",
    }
    token = jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")
    panel_base = os.getenv("PANEL_BASE_URL", "https://app.rbt-crm.ru")
    return f"{panel_base}/panel?token={token}"


class UnifiedDialogService:
    def __init__(self):
        self._sessions: Dict[int, DialogContext] = {}

    def _get_ctx(self, user_id: int) -> DialogContext:
        if user_id not in self._sessions:
            self._sessions[user_id] = DialogContext()
        return self._sessions[user_id]

    def reset(self, user_id: int) -> None:
        self._sessions.pop(user_id, None)

    def _inline_keyboard(self, rows: List[List[dict]]) -> List[dict]:
        return [
            {
                "type": "inline_keyboard",
                "payload": {"buttons": rows},
            }
        ]

    async def show_main_menu(self, user_id: int) -> Tuple[str, Optional[List[dict]]]:
        """Показывает главное меню для активного пользователя"""

        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(Master).where(Master.max_user_id == user_id)
            )
            master = result.scalar_one_or_none()

            if not master:
                return (
                    "❌ Ошибка: пользователь не найден. Пройдите регистрацию заново.",
                    None,
                )

        # Формируем обращение
        if master.name:
            greeting = f"{master.name} {master.lastname or ''}".strip()
        elif master.service_name:
            greeting = master.service_name
        else:
            greeting = "пользователь"

        kb = self._inline_keyboard(
            [
                [
                    {
                        "type": "callback",
                        "text": "📝 Новая заявка",
                        "payload": "menu:new_request",
                        "intent": "default",
                    }
                ]
            ]
        )

        text = (
            f"👋 Добро пожаловать, {greeting}!\n\n"
            f"Нажмите кнопку или введите /start, чтобы оформить заявку."
        )

        return text, kb

    async def start_new_request(self, user_id: int) -> Tuple[str, Optional[List[dict]]]:
        """Начинает новый диалог создания заявки"""

        self.reset(user_id)
        ctx = self._get_ctx(user_id)
        ctx.state = DialogState.ADDRESS_MODE

        return self._ask_address_mode()

    async def start_or_reset(self, user_id: int) -> Tuple[str, Optional[List[dict]]]:
        """Начинает новый диалог или сбрасывает текущий (для webhook)"""
        self.reset(user_id)

        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(Master).where(Master.max_user_id == user_id)
            )
            master = result.scalar_one_or_none()

        if not master or master.is_active == 0:
            return await registration_service.start_registration(user_id)

        return await self.start_new_request(user_id)

    def _ask_address_mode(self) -> Tuple[str, List[dict]]:
        """Спрашивает, где выполнять работу: мастерская или выезд"""
        kb = self._inline_keyboard(
            [
                [
                    {
                        "type": "callback",
                        "text": "Мастерская",
                        "payload": "address_mode:workshop",
                        "intent": "default",
                    },
                    {
                        "type": "callback",
                        "text": "Выезд к клиенту",
                        "payload": "address_mode:enter_address",
                        "intent": "default",
                    },
                ]
            ]
        )
        return "Где будет выполняться работа?", kb

    def _buttons_private_house(self) -> List[dict]:
        return self._inline_keyboard(
            [
                [
                    {
                        "type": "callback",
                        "text": "Частный дом",
                        "payload": "address_details:private_house",
                        "intent": "default",
                    }
                ]
            ]
        )

    async def _get_booked_slots_for_date(
        self, master_id: int, date_str: str
    ) -> set[str]:
        """Возвращает множество занятых временных слотов для мастера на указанную дату"""
        target_date = datetime.strptime(date_str, "%Y-%m-%d").date()

        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(ServiceRequest.time_slot).where(
                    ServiceRequest.master_id == master_id,
                    ServiceRequest.date_iso == target_date,
                    ServiceRequest.status.in_(["new", "in_work", "confirmed"]),
                )
            )
            booked_slots = set()
            for row in result:
                if row[0]:
                    booked_slots.add(f"slot_time:{date_str}:{row[0]}")
            return booked_slots

    async def _has_any_free_slot(self, master_id: int, date_str: str) -> bool:
        """Проверяет, есть ли хотя бы один свободный слот на указанную дату"""
        booked = await self._get_booked_slots_for_date(master_id, date_str)
        for start, end in TIME_SLOTS:
            time_slot = f"{start}-{end}"
            payload = f"slot_time:{date_str}:{time_slot}"
            if payload not in booked:
                return True
        return False

    def _build_slot_date_options(self) -> List[dict]:
        today = datetime.now().date()
        options: List[dict] = []
        for offset in range(6):
            d = today + timedelta(days=offset)
            iso_str = d.isoformat()
            wd_short = WEEKDAY_SHORT_RU[d.weekday()]
            if offset == 0:
                label = "Сегодня"
            elif offset == 1:
                label = "Завтра"
            else:
                label = f"{wd_short.capitalize()}, {d.strftime('%d.%m')}"
            options.append({"text": label, "payload": f"slot:{iso_str}"})
        return options

    def _buttons_slot_dates(self) -> List[dict]:
        options = self._build_slot_date_options()
        row1 = options[0:3]
        row2 = options[3:6]

        rows: List[List[dict]] = []
        if row1:
            rows.append(
                [
                    {
                        "type": "callback",
                        "text": opt["text"],
                        "payload": opt["payload"],
                        "intent": "default",
                    }
                    for opt in row1
                ]
            )
        if row2:
            rows.append(
                [
                    {
                        "type": "callback",
                        "text": opt["text"],
                        "payload": opt["payload"],
                        "intent": "default",
                    }
                    for opt in row2
                ]
            )

        return self._inline_keyboard(rows)

    async def _buttons_time_slots(self, master_id: int, date_str: str) -> List[dict]:
        """Показывает кнопки с временными слотами, помечая занятые"""
        booked = await self._get_booked_slots_for_date(master_id, date_str)
        buttons: List[dict] = []
        for start, end in TIME_SLOTS:
            time_slot = f"{start}-{end}"
            payload = f"slot_time:{date_str}:{time_slot}"
            if payload in booked:
                text = "🔴 ЗАНЯТО"
            else:
                text = f"{start}-{end}"
            buttons.append(
                {
                    "type": "callback",
                    "text": text,
                    "payload": payload,
                    "intent": "default",
                }
            )
        rows: List[List[dict]] = []
        for i in range(0, len(buttons), 3):
            rows.append(buttons[i : i + 3])
        return self._inline_keyboard(rows)

    def _format_pretty_date(self, date_str: str) -> str:
        d = datetime.strptime(date_str, "%Y-%m-%d").date()
        weekday = WEEKDAY_FULL_RU[d.weekday()]
        return f"{weekday}, {d.strftime('%d.%m.%y')}"

    def _normalize_phone(self, raw: str) -> Optional[str]:
        digits = "".join(ch for ch in raw if ch.isdigit())
        if len(digits) == 11 and (digits.startswith("7") or digits.startswith("8")):
            return "+7" + digits[1:]
        if len(digits) == 11 and digits.startswith("9"):
            return "+7" + digits
        if len(digits) == 10 and digits.startswith("9"):
            return "+7" + digits
        return None

    def _build_yandex_url(self, address: Optional[str]) -> Optional[str]:
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

    # Описание
    details_str = comment or ""
    if address_details:
        details_str += f" ({address_details})"

    # Телефон в формате 8XXXXXXXXXX
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

    # ВАЖНО: создаём details_param, которой не хватало
    details_param = details_str.replace(" ", "+")

    # Дата / время
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
            start_dt = datetime.combine(
                d.date(), datetime.strptime(start_str, "%H:%M").time()
            )
            end_dt = datetime.combine(
                d.date(), datetime.strptime(end_str, "%H:%M").time()
            )
        except ValueError:
            start_dt = d
            end_dt = d + timedelta(hours=1)
    else:
        start_dt = datetime.combine(
            d.date(), datetime.strptime("10:00", "%H:%M").time()
        )
        end_dt = start_dt + timedelta(hours=1)

    dates_param = (
        f"{start_dt.strftime('%Y%m%dT%H%M00')}/{end_dt.strftime('%Y%m%dT%H%M00')}"
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

    def _ask_name(self) -> Tuple[str, List[dict]]:
        """Запрашивает имя клиента с кнопкой 'Неизвестно'."""
        kb = self._inline_keyboard(
            [
                [
                    {
                        "type": "callback",
                        "text": "❓ Неизвестно / Без имени",
                        "payload": "name:unknown",
                        "intent": "default",
                    }
                ]
            ]
        )
        return "👤 Введи имя контактного лица:", kb

    async def handle_callback(
        self, user_id: int, payload: str
    ) -> Tuple[str, Optional[List[dict]]]:
        """Обработка callback-запросов"""

        print(f"🔔 handle_callback: user_id={user_id}, payload={payload}")

        # Callback от регистрации
        if payload == "registration:start" or payload.startswith("role:"):
            return await registration_service.handle_callback(user_id, payload)

        # Кнопка "Новая заявка"
        if payload == "menu:new_request":
            async with AsyncSessionLocal() as session:
                result = await session.execute(
                    select(Master).where(
                        Master.max_user_id == user_id, Master.is_active == 1
                    )
                )
                master = result.scalar_one_or_none()

            if not master:
                return await registration_service.start_registration(user_id)

            return await self.start_new_request(user_id)

        # Проверяем, зарегистрирован ли пользователь
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(Master).where(
                    Master.max_user_id == user_id, Master.is_active == 1
                )
            )
            master = result.scalar_one_or_none()

        if not master:
            return await registration_service.start_registration(user_id)

        ctx = self._get_ctx(user_id)

        # Выбор места работы
        if payload == "address_mode:workshop" and ctx.state == DialogState.ADDRESS_MODE:
            ctx.address = "Мастерская"
            ctx.address_details = None
            ctx.state = DialogState.DESCRIPTION
            return (
                "Понял, работа в мастерской.\n"
                "Опиши поломку со слов клиента.",
                None,
            )

        if (
            payload == "address_mode:enter_address"
            and ctx.state == DialogState.ADDRESS_MODE
        ):
            ctx.state = DialogState.ADDRESS
            return "Введи полный адрес (город, улица, дом):", None

        if (
            payload == "address_details:private_house"
            and ctx.state == DialogState.ADDRESS_DETAILS
        ):
            ctx.address_details = None
            ctx.state = DialogState.DESCRIPTION
            return "✅ Адрес сохранен. Опиши поломку со слов клиента:", None

        # Выбор даты
        if payload.startswith("slot:") and ctx.state == DialogState.SLOT:
            date_str = payload.split(":", 1)[1]
            ctx.date_iso = date_str
            ctx.date = self._format_pretty_date(date_str)
            ctx.slot = None
            ctx.state = DialogState.SLOT_TIME

            async with AsyncSessionLocal() as session:
                result = await session.execute(
                    select(Master).where(Master.max_user_id == user_id)
                )
                master = result.scalar_one_or_none()
                master_id = master.id if master else None

            # Проверяем, есть ли хоть один свободный слот на выбранную дату
            if not await self._has_any_free_slot(master_id, date_str):
                return (
                    f"❌ На {ctx.date} нет свободных временных слотов.\nВыберите другую дату:",
                    self._buttons_slot_dates(),
                )

            return (
                f"Выбери доступное время для {ctx.date}:",
                await self._buttons_time_slots(master_id, date_str),
            )

        # Выбор времени
        if payload.startswith("slot_time:") and ctx.state == DialogState.SLOT_TIME:
            _, rest = payload.split(":", 1)
            try:
                date_part, time_part = rest.split(":", 1)
            except ValueError:
                ctx.slot = rest
                ctx.state = DialogState.NAME
                return self._ask_name()

            async with AsyncSessionLocal() as session:
                result = await session.execute(
                    select(Master).where(Master.max_user_id == user_id)
                )
                master = result.scalar_one_or_none()
                master_id = master.id if master else None

            booked = await self._get_booked_slots_for_date(master_id, date_part)
            payload_full = f"slot_time:{date_part}:{time_part}"
            if payload_full in booked:
                return (
                    "Увы, этот слот уже занят. Выбери, пожалуйста, другой:",
                    await self._buttons_time_slots(master_id, date_part),
                )

            ctx.slot = time_part
            ctx.state = DialogState.NAME
            return self._ask_name()

        # Обработка кнопки "Неизвестно" для имени
        if payload == "name:unknown" and ctx.state == DialogState.NAME:
            ctx.name = "Без имени"
            ctx.state = DialogState.PHONE
            return "☎️ Введи номер контактного лица:", None

        return (
            "Команда уже не актуальна. Напиши, пожалуйста, текстом, что хочешь сделать.",
            None,
        )

    async def handle_message(self, user_id: int, text: str) -> Tuple[str, Optional[List[dict]]]:
        """Обработка текстовых сообщений"""

        if registration_service.is_in_registration(user_id):
            return await registration_service.handle_message(user_id, text)

        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(Master).where(
                    Master.max_user_id == user_id, Master.is_active == 1
                )
            )
            master = result.scalar_one_or_none()

        if not master:
            return await registration_service.start_registration(user_id)

        ctx = self._get_ctx(user_id)
        text_clean = text.strip()
        text_lower = text_clean.lower()

        if text_lower in ("/cancel", "отмена", "стоп"):
            return await self.cancel_request(user_id)

        if text_lower in ("/start", "новая заявка", "заявка"):
            self.reset(user_id)
            return await self.start_new_request(user_id)

        # Ввод адреса
        if ctx.state == DialogState.ADDRESS_MODE:
            ctx.address = text_clean
            ctx.state = DialogState.ADDRESS_DETAILS
            return (
                "✅ Адрес сохранен.\n"
                "Уточни квартиру, этаж и подъезд. Например, кв1 п2 эт3\n"
                "Если это частный дом, то нажми «Частный дом».",
                self._buttons_private_house(),
            )

        if ctx.state == DialogState.ADDRESS:
            ctx.address = text_clean
            ctx.state = DialogState.ADDRESS_DETAILS
            return (
                "✅ Адрес сохранен.\n"
                "Уточни квартиру, этаж и подъезд. Например, кв1 п2 эт3\n"
                "Если это частный дом, то нажми «Частный дом».",
                self._buttons_private_house(),
            )

        if ctx.state == DialogState.ADDRESS_DETAILS:
            if text_clean == "Частный дом":
                ctx.address_details = None
            else:
                ctx.address_details = text_clean
            ctx.state = DialogState.DESCRIPTION
            return (
                "✅ Частный дом.\nНапиши причину бращения со слов клиента:",
                None,
            )

        # Ввод описания
        if ctx.state == DialogState.DESCRIPTION:
            ctx.description = text_clean
            ctx.state = DialogState.SLOT
            return (
                "✅ Принял описание. Выбери подходящую дату\n"
                "Если подходящей даты нет в списке, введи её в формате ДД.ММ.ГГ (например, 31.12.24):",
                self._buttons_slot_dates(),
            )

        # Обработка ручного ввода даты
        if ctx.state == DialogState.SLOT:
            iso_date = self._parse_date_from_text(text_clean)
            if iso_date:
                ctx.date_iso = iso_date
                ctx.date = self._format_pretty_date(iso_date)
                ctx.slot = None
                ctx.state = DialogState.SLOT_TIME

                async with AsyncSessionLocal() as session:
                    result = await session.execute(
                        select(Master).where(Master.max_user_id == user_id)
                    )
                    master = result.scalar_one_or_none()
                    master_id = master.id if master else None

                if not await self._has_any_free_slot(master_id, iso_date):
                    return (
                        f"❌ На {ctx.date} нет свободных временных слотов.\nПожалуйста, выберите другую дату:",
                        self._buttons_slot_dates(),
                    )

                return (
                    f"Выбери удобное время для {ctx.date}:",
                    await self._buttons_time_slots(master_id, iso_date),
                )
            else:
                return (
                    "Не удалось распознать дату. Используйте формат ДД.ММ.ГГ или ДД.ММ.ГГГГ.\n"
                    "Например: 31.12.24 или 31.12.2024",
                    self._buttons_slot_dates(),
                )

        if ctx.state == DialogState.SLOT_TIME:
            # Если пользователь вводит время текстом (не через кнопки), просим выбрать из кнопок
            return (
                "Пожалуйста, выберите время из кнопок ниже:",
                await self._buttons_time_slots(master_id, ctx.date_iso),
            )

        # Ввод имени
        if ctx.state == DialogState.NAME:
            ctx.name = text_clean if text_clean.strip() else "Без имени"
            ctx.state = DialogState.PHONE
            return "☎️ Введи номер контактного лица.", None

        # Ввод телефона
        if ctx.state == DialogState.PHONE:
            normalized = self._normalize_phone(text_clean)
            if not normalized:
                return (
                    "Похоже, номер в непонятном формате.\n"
                    "Введи, пожалуйста, мобильный номер в формате 8ХХХХХХХХХХ или +7ХХХХХХХХХХ.\n"
                    "Попробуй ещё раз:",
                    None,
                )
            ctx.phone = normalized
            ctx.state = DialogState.CONFIRMED

            async with AsyncSessionLocal() as session:
                result = await session.execute(
                    select(Master).where(Master.max_user_id == user_id)
                )
                master_obj = result.scalar_one_or_none()

                if not master_obj:
                    return (
                        "❌ Ошибка: мастер не найден. Пройдите регистрацию заново.",
                        None,
                    )

                master_id = master_obj.id

                data = {
                    "user_id": user_id,
                    "chat_id": user_id,
                    "client_id": None,
                    "client_name": ctx.name,
                    "client_phone": ctx.phone,
                    "service_title": "Заявка",
                    "problem_description": ctx.description,
                    "location_type": "workshop"
                    if ctx.address == "Мастерская"
                    else "client_address",
                    "address": "Мастерская"
                    if ctx.address == "Мастерская"
                    else ctx.address,
                    "address_details": ctx.address_details,
                    "date_iso": ctx.date_iso,
                    "time_slot": ctx.slot,
                    "datetime_from": None,
                    "datetime_to": None,
                    "total_amount": None,
                    "currency": "RUB",
                    "payment_status": "unpaid",
                    "meta": None,
                    "master_id": master_id,
                    "assigned_master_id": master_id,  # создатель = исполнитель
                }

                req = await create_service_request(session, data)

            ctx.request_id = req.id

            await notify_master_request_created(req.id)

            # ====== 1. Ряд: Добавить в календарь ======
            row1 = []
            date_iso_str = ctx.date_iso if ctx.date_iso else None

            # В календарь передаём именно мастерский номер
            google_cal_url = _build_google_calendar_url(
                order_no=req.master_seq if req.master_seq is not None else None,
                date_iso=date_iso_str,
                time_slot=ctx.slot,
                address=ctx.address,
                address_details=ctx.address_details,
                comment=ctx.description,
                phone=ctx.phone,
            )
            if google_cal_url:
                row1.append(
                    {
                        "type": "link",
                        "text": "📅 Добавить в календарь",
                        "url": google_cal_url,
                    }
                )
            else:
                row1.append(
                    {
                        "type": "callback",
                        "text": "❌ Нет данных для календаря",
                        "payload": "noop",
                    }
                )

            # ====== 2. Ряд: Открыть в боте и Открыть в CRM ======
            row2 = []

            order_bot_url = os.getenv("MAX_ORDER_BOT_LINK", "")
            row2.append(
                {
                    "type": "link",
                    "text": "📋 Открыть заявки",
                    "url": order_bot_url,
                }
            )

            panel_base = os.getenv("PANEL_BASE_URL", "https://app.rbt-crm.ru")
            view_request_url = f"{panel_base}/requests/{req.id}"
            row2.append(
                {
                    "type": "link",
                    "text": "🌐 Перейти в CRM",
                    "url": view_request_url,
                }
            )

            # ====== 3. Ряд: Создать новую заявку ======
            row3 = [
                {
                    "type": "callback",
                    "text": "📝 Новая заявка",
                    "payload": "menu:new_request",
                    "intent": "default",
                }
            ]

            kb = self._inline_keyboard([row1, row2, row3])

            # Мастеру показываем только master_seq
            if req.master_seq is not None:
                display_number = req.master_seq
                reply = (
                    f"✅ Заявка №{display_number} успешно создана! Выберите действие:"
                )
            else:
                reply = "✅ Заявка успешно создана! Выберите действие:"

            self.reset(user_id)
            return reply, kb

        return await self.show_main_menu(user_id)

    async def cancel_request(self, user_id: int) -> Tuple[str, Optional[List[dict]]]:
        """Отменяет текущую заявку и предлагает создать новую"""
        self.reset(user_id)

        kb = self._inline_keyboard(
            [
                [
                    {
                        "type": "callback",
                        "text": "Создать новую заявку",
                        "payload": "menu:new_request",
                        "intent": "default",
                    }
                ]
            ]
        )

        text = (
            "❌ Заявка отменена.\n\n"
            "Вы можете создать новую заявку, нажав на кнопку ниже."
        )

        return text, kb


dialog_service = UnifiedDialogService()