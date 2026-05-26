"""Сервис диалогов для Max бота (Диспетчер)"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, Optional, List, Tuple
import os

from max_client import MaxClient, MAX_APPLICATIONS_CHAT_ID

from app.db.session import AsyncSessionLocal
from app.services.requests import create_service_request
from app.services.devices import list_categories, list_subtypes_by_category
from app.services.masters_notify import notify_master_request_created
from app.services.registration_service import registration_service

from app.db.models import Master

from sqlalchemy import select


class DialogState:
    CHOOSE_CATEGORY = "choose_category"
    CHOOSE_SUBTYPE = "choose_subtype"
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
    state: str = DialogState.CHOOSE_CATEGORY

    chat_id: Optional[int] = None
    main_category: Optional[str] = None
    subtype: Optional[str] = None
    service_title: Optional[str] = None
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

MY_USER_ID = int(os.getenv("MAX_OWNER_USER_ID", "0"))


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

    # ========== ГЛАВНОЕ МЕНЮ ДЛЯ ЗАРЕГИСТРИРОВАННЫХ ПОЛЬЗОВАТЕЛЕЙ ==========
    
    async def show_main_menu(self, user_id: int) -> Tuple[str, Optional[List[dict]]]:
        """Показывает главное меню для активного пользователя"""
        
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(Master).where(Master.max_user_id == user_id)
            )
            master = result.scalar_one_or_none()
            
            if not master:
                return "❌ Ошибка: пользователь не найден. Пройдите регистрацию заново.", None
        
        kb = self._inline_keyboard([[
            {
                "type": "callback",
                "text": "📝 Новая заявка",
                "payload": "menu:new_request",
                "intent": "default",
            }
        ]])
        
        text = (
            f"👋 Добро пожаловать, {master.name or master.service_name or 'пользователь'}!\n\n"
            f"Нажмите кнопку или введите /start, чтобы оформить заявку."
        )
        
        return text, kb
    
    # ========== НАЧАЛО НОВОЙ ЗАЯВКИ ==========
    
    async def start_new_request(self, user_id: int) -> Tuple[str, Optional[List[dict]]]:
        """Начинает новый диалог создания заявки"""
        
        # Сбрасываем предыдущий диалог
        self.reset(user_id)
        ctx = self._get_ctx(user_id)
        ctx.state = DialogState.CHOOSE_CATEGORY
        
        async with AsyncSessionLocal() as session:
            categories = await list_categories(session)
        
        # Вертикальные категории
        rows: List[List[dict]] = []
        for cat in categories:
            rows.append([
                {
                    "type": "callback",
                    "text": cat.name,
                    "payload": f"cat:{cat.code}",
                    "intent": "default",
                }
            ])
        
        kb = self._inline_keyboard(rows)
        return "Выберите категорию техники:", kb
    
    # ========== ОСТАЛЬНЫЕ МЕТОДЫ (без изменений) ==========
    
    
    def _buttons_address_mode(self) -> List[dict]:
        return self._inline_keyboard(
            [[
                {
                    "type": "callback",
                    "text": "Мастерская",
                    "payload": "address_mode:workshop",
                    "intent": "default",
                },
                {
                    "type": "callback",
                    "text": "Ввести адрес",
                    "payload": "address_mode:enter_address",
                    "intent": "default",
                },
            ]]
        )

    def _buttons_private_house(self) -> List[dict]:
        return self._inline_keyboard(
            [[
                {
                    "type": "callback",
                    "text": "Частный дом",
                    "payload": "address_details:private_house",
                    "intent": "default",
                }
            ]]
        )

    async def _get_booked_slots_for_date(self, date_str: str) -> set[str]:
        return set()

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
            rows.append([
                {
                    "type": "callback",
                    "text": opt["text"],
                    "payload": opt["payload"],
                    "intent": "default",
                }
                for opt in row1
            ])
        if row2:
            rows.append([
                {
                    "type": "callback",
                    "text": opt["text"],
                    "payload": opt["payload"],
                    "intent": "default",
                }
                for opt in row2
            ])

        return self._inline_keyboard(rows)

    async def _buttons_time_slots(self, date_str: str) -> List[dict]:
        booked = await self._get_booked_slots_for_date(date_str)
        buttons: List[dict] = []
        for start, end in TIME_SLOTS:
            payload = f"slot_time:{date_str}:{start}-{end}"
            text = "ЗАНЯТО" if payload in booked else f"{start}-{end}"
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
        self,
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

    # ========== ОСНОВНЫЕ МЕТОДЫ ДИАЛОГА ==========

    async def handle_callback(self, user_id: int, payload: str) -> Tuple[str, Optional[List[dict]]]:
        """Обработка callback-запросов"""
        
        # Кнопка "Новая заявка" из главного меню
        if payload == "menu:new_request":
            return await self.start_new_request(user_id)
        
        ctx = self._get_ctx(user_id)
        
        # категория
        if payload.startswith("cat:"):
            category_code = payload.split(":", 1)[1]
            ctx.main_category = category_code
            ctx.state = DialogState.CHOOSE_SUBTYPE

            async with AsyncSessionLocal() as session:
                subtypes = await list_subtypes_by_category(session, category_code)

            rows: List[List[dict]] = []
            for st in subtypes:
                rows.append([
                    {
                        "type": "callback",
                        "text": st.name,
                        "payload": f"sub:{st.code}",
                        "intent": "default",
                    }
                ])
            kb = self._inline_keyboard(rows)
            return "Выберите вид техники:", kb

        # подтип
        if payload.startswith("sub:"):
            subtype_code = payload.split(":", 1)[1]
            ctx.subtype = subtype_code
            ctx.state = DialogState.ADDRESS_MODE
            ctx.service_title = subtype_code

            text = (
                f"Записал: {ctx.service_title}.\n"
                "Где выполнить услугу?\n"
                "— Нажми «Мастерская», если привезёшь сам\n"
                "— Нажми «Ввести адрес», чтобы ввести адрес вручную\n"
                "Или просто отправь адрес текстом."
            )
            return text, self._buttons_address_mode()

        # режим адреса
        if payload == "address_mode:workshop" and ctx.state == DialogState.ADDRESS_MODE:
            ctx.address = "Мастерская"
            ctx.address_details = None
            ctx.state = DialogState.DESCRIPTION
            return (
                "Понял, работа в мастерской.\n"
                "Опиши, пожалуйста, что нужно сделать (детально).",
                None,
            )

        if payload == "address_mode:enter_address" and ctx.state == DialogState.ADDRESS_MODE:
            ctx.state = DialogState.ADDRESS
            return "Хорошо, введи, пожалуйста, полный адрес (улица, дом, город).", None

        if payload == "address_details:private_house" and ctx.state == DialogState.ADDRESS_DETAILS:
            ctx.address_details = None
            ctx.state = DialogState.DESCRIPTION
            return (
                "Принял. Теперь опиши, пожалуйста, что нужно сделать (детально).",
                None,
            )

        if payload.startswith("slot:") and ctx.state == DialogState.SLOT:
            date_str = payload.split(":", 1)[1]
            ctx.date_iso = date_str
            ctx.date = self._format_pretty_date(date_str)
            ctx.slot = None
            ctx.state = DialogState.SLOT_TIME
            return (
                f"Выбери удобное время для {ctx.date}:",
                await self._buttons_time_slots(date_str),
            )

        if payload.startswith("slot_time:") and ctx.state == DialogState.SLOT_TIME:
            _, rest = payload.split(":", 1)
            try:
                date_part, time_part = rest.split(":", 1)
            except ValueError:
                ctx.slot = rest
                ctx.state = DialogState.NAME
                return "Ок. Как к тебе обращаться?", None

            booked = await self._get_booked_slots_for_date(date_part)
            payload_full = f"slot_time:{date_part}:{time_part}"
            if payload_full in booked:
                return (
                    "Увы, этот слот уже занят. Выбери, пожалуйста, другой:",
                    await self._buttons_time_slots(date_part),
                )

            ctx.slot = time_part
            ctx.state = DialogState.NAME
            return "Ок. Как к тебе обращаться?", None

        return (
            "Команда уже не актуальна. Напиши, пожалуйста, текстом, что хочешь сделать.",
            None,
        )

    async def handle_message(self, user_id: int, text: str) -> Tuple[str, Optional[List[dict]]]:
        """Обработка текстовых сообщений"""
        
        # Проверяем, активен ли пользователь
        is_active = await registration_service.is_user_active(user_id)
        
        if not is_active:
            # Отправляем на регистрацию
            return await registration_service.handle_message(user_id, text)
        
        ctx = self._get_ctx(user_id)
        text_clean = text.strip()
        text_lower = text_clean.lower()

        if text_lower in ("/cancel", "отмена", "стоп"):
            self.reset(user_id)
            return await self.show_main_menu(user_id)

        if text_lower in ("/start", "новая заявка", "заявка"):
            return await self.start_new_request(user_id)

        # После выбора подтипа весь текст идёт по шагам
        if ctx.state == DialogState.ADDRESS_MODE:
            ctx.address = text_clean
            ctx.state = DialogState.ADDRESS_DETAILS
            return (
                "Адрес записал.\n"
                "Уточни, пожалуйста, квартиру и подъезд.\n"
                "Если это частный дом, нажми «Частный дом» или напиши эти слова.",
                self._buttons_private_house(),
            )

        if ctx.state == DialogState.ADDRESS:
            ctx.address = text_clean
            ctx.state = DialogState.ADDRESS_DETAILS
            return (
                "Адрес записал.\n"
                "Уточни, пожалуйста, квартиру и подъезд.\n"
                "Если это частный дом, нажми «Частный дом» или напиши эти слова.",
                self._buttons_private_house(),
            )

        if ctx.state == DialogState.ADDRESS_DETAILS:
            if text_clean == "Частный дом":
                ctx.address_details = None
            else:
                ctx.address_details = text_clean
            ctx.state = DialogState.DESCRIPTION
            return "Принял. Теперь опиши, пожалуйста, что нужно сделать (детально).", None

        if ctx.state == DialogState.DESCRIPTION:
            ctx.description = text_clean
            ctx.state = DialogState.SLOT
            return (
                "Принял описание. Когда удобно выполнить услугу?\n"
                "Можешь выбрать один из ближайших дней ниже или написать дату и время текстом.",
                self._buttons_slot_dates(),
            )

        if ctx.state in (DialogState.SLOT, DialogState.SLOT_TIME):
            ctx.date_iso = None
            ctx.date = None
            ctx.slot = text_clean
            ctx.state = DialogState.NAME
            return "Ок. Как к тебе обращаться?", None

        if ctx.state == DialogState.NAME:
            ctx.name = text_clean
            ctx.state = DialogState.PHONE
            return "Спасибо. Оставь, пожалуйста, номер телефона для связи (мобильный).", None

        if ctx.state == DialogState.PHONE:
            normalized = self._normalize_phone(text_clean)
            if not normalized:
                return (
                    "Похоже, номер в непонятном формате.\n"
                    "Введи, пожалуйста, мобильный номер в формате 8ХХХХХХХХХХ или +7ХХХХХХХХХХ.",
                    None,
                )
            ctx.phone = normalized
            ctx.state = DialogState.CONFIRMED

            async with AsyncSessionLocal() as session:
                # Получаем мастера
                result = await session.execute(
                    select(Master).where(Master.max_user_id == user_id)
                )
                master_obj = result.scalar_one_or_none()

                if not master_obj:
                    return "❌ Ошибка: мастер не найден. Пройдите регистрацию заново.", None

                master_id = master_obj.id

                data = {
                    "user_id": user_id,
                    "chat_id": user_id,
                    "client_id": None,
                    "client_name": ctx.name,
                    "client_phone": ctx.phone,
                    "main_category": ctx.main_category,
                    "subtype": ctx.subtype,
                    "custom_device": None,
                    "service_title": ctx.service_title or ctx.subtype,
                    "problem_description": ctx.description,
                    "location_type": "workshop" if ctx.address == "Мастерская" else "client_address",
                    "address": "Мастерская" if ctx.address == "Мастерская" else ctx.address,
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
                }

                req = await create_service_request(session, data)

            ctx.request_id = req.id

            # Отправляем в общий канал заявок
            await self._send_application_to_channel(user_id, ctx)

            # Отправляем мастеру
            await notify_master_request_created(req.id)

            reply = f"✅ Спасибо, заявка №{req.id} создана! Мастер скоро свяжется с вами."
            self.reset(user_id)
            return reply, None

        # Если текст прилетел в неизвестном состоянии — показываем главное меню
        return await self.show_main_menu(user_id)

    async def _send_application_to_channel(self, user_id: int, ctx: DialogContext) -> None:
        """Отправляет заявку в общий канал"""
        request_no = ctx.request_id if ctx.request_id is not None else "—"
        created_at = datetime.now().strftime("%d.%m.%y")
        lines = [f"📝 Заявка № {request_no} от {created_at}"]

        if user_id != MY_USER_ID:
            lines.append(f"👤 Пользователь ID: {user_id}")

        lines.append(f"🔧 Услуга: {ctx.service_title or ctx.subtype or '—'}")

        if ctx.address == "Мастерская":
            lines.append("🏭 Место выполнения: мастерская")
        elif ctx.address:
            lines.append(f"📍 Адрес: {ctx.address}")
        else:
            lines.append("📍 Адрес: не указан")

        if ctx.address_details:
            lines.append(f"📌 Уточнение по адресу: {ctx.address_details}")

        if ctx.date:
            lines.append(f"📅 Дата: {ctx.date}")
        if ctx.slot:
            lines.append(f"⏰ Время/слот: {ctx.slot}")

        lines.append(f"📄 Описание: {ctx.description or '—'}")
        lines.append(f"🙋‍♂️ Имя: {ctx.name or '—'}")
        lines.append(f"📞 Телефон: {ctx.phone or '—'}")

        text = "\n".join(lines)

        yandex_url = self._build_yandex_url(ctx.address)
        google_url = self._build_google_calendar_url(
            order_no=ctx.request_id,
            date_iso=ctx.date_iso,
            time_slot=ctx.slot,
            address=ctx.address,
            address_details=ctx.address_details,
            comment=ctx.description,
            phone=ctx.phone,
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

        client = MaxClient()
        await client.send_text_to_chat(
            chat_id=MAX_APPLICATIONS_CHAT_ID,
            text=text,
            attachments=attachments,
        )
        await client.close()

    async def start_or_reset(self, user_id: int) -> Tuple[str, Optional[List[dict]]]:
        """Начинает новый диалог или сбрасывает текущий (для webhook)"""
        self.reset(user_id)
        is_active = await registration_service.is_user_active(user_id)
        
        if not is_active:
            return await registration_service.start_registration(user_id)
        
        return await self.show_main_menu(user_id)

dialog_service = UnifiedDialogService()