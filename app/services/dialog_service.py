from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, Optional, List, Tuple

from max_client import MaxClient, MAX_APPLICATIONS_CHAT_ID


class DialogState:
    IDLE = "idle"
    SERVICE = "service"
    ADDRESS_MODE = "address_mode"        # выбор: мастерская / ввод адреса / сразу текстом
    ADDRESS = "address"                  # ввод адреса
    ADDRESS_DETAILS = "address_details"  # кв/подъезд
    DESCRIPTION = "description"
    SLOT = "slot"                        # выбор даты
    SLOT_TIME = "slot_time"              # выбор времени
    NAME = "name"
    PHONE = "phone"
    CONFIRMED = "confirmed"


@dataclass
class DialogContext:
    state: str = DialogState.IDLE
    service: Optional[str] = None
    address: Optional[str] = None
    address_details: Optional[str] = None  # кв/подъезд/этаж и т.п.
    description: Optional[str] = None
    date: Optional[str] = None             # красивая дата: "Четверг, 15.05.26"
    slot: Optional[str] = None             # время/слот: "09:00-10:00"
    name: Optional[str] = None
    phone: Optional[str] = None


# Пн=0 ... Вс=6
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

# 9 часовых слотов
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


class DialogService:
    def __init__(self):
        self._sessions: Dict[int, DialogContext] = {}

    def _get_ctx(self, user_id: int) -> DialogContext:
        if user_id not in self._sessions:
            self._sessions[user_id] = DialogContext(state=DialogState.SERVICE)
        return self._sessions[user_id]

    def _normalize_phone(self, raw: str) -> Optional[str]:
        digits = "".join(ch for ch in raw if ch.isdigit())
        if len(digits) == 11 and (digits.startswith("7") or digits.startswith("8")):
            return "+7" + digits[1:]
        if len(digits) == 11 and digits.startswith("9"):
            return "+7" + digits
        if len(digits) == 10 and digits.startswith("9"):
            return "+7" + digits
        return None

    def _format_pretty_date(self, date_str: str) -> str:
        """
        '2026-05-15' -> 'Четверг, 15.05.26'
        """
        d = datetime.strptime(date_str, "%Y-%m-%d").date()
        weekday = WEEKDAY_FULL_RU[d.weekday()]
        return f"{weekday}, {d.strftime('%d.%m.%y')}"

    # ---------- Заглушка БД для занятых слотов ----------

    async def _get_booked_slots_for_date(self, date_str: str) -> set[str]:
        """
        TODO: заменить на реальный запрос к БД.

        Должна возвращать множество payload'ов занятых слотов вида:
        'slot_time:YYYY-MM-DD:09:00-10:00'
        """
        return set()

    # ---------- Кнопки ----------

    def _inline_keyboard(self, rows: List[List[dict]]) -> List[dict]:
        # rows: список рядов; в каждом ряду — список кнопок
        return [
            {
                "type": "inline_keyboard",
                "payload": {
                    "buttons": rows,
                },
            }
        ]

    def _buttons_address_mode(self) -> List[dict]:
        return self._inline_keyboard(
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
                        "text": "Ввести адрес",
                        "payload": "address_mode:enter_address",
                        "intent": "default",
                    },
                ]
            ]
        )

    def _buttons_private_house(self) -> List[dict]:
        return self._inline_keyboard(
            [
                [
                    {
                        "type": "callback",
                        "text": "Частный дом",
                        "payload": "address_details:private_house",
                        "intent": "default",
                    },
                ]
            ]
        )

    def _build_slot_options(self) -> List[dict]:
        """
        Строит список слотов на ближайшие 6 дней:
        [
          {"text": "Сегодня", "payload": "slot:2026-05-12"},
          {"text": "Завтра", "payload": "slot:2026-05-13"},
          {"text": "Чт, 15.05", "payload": "slot:2026-05-15"},
          ...
        ]
        """
        today = datetime.now().date()
        options: List[dict] = []

        for offset in range(6):
            d = today + timedelta(days=offset)
            iso_str = d.isoformat()  # 2026-05-12
            weekday_idx = d.weekday()  # Monday=0
            wd_short = WEEKDAY_SHORT_RU[weekday_idx]
            if offset == 0:
                label = "Сегодня"
            elif offset == 1:
                label = "Завтра"
            else:
                label = f"{wd_short.capitalize()}, {d.strftime('%d.%m')}"

            options.append(
                {
                    "text": label,
                    "payload": f"slot:{iso_str}",
                }
            )

        return options

    def _buttons_slot_dates(self) -> List[dict]:
        """
        Клавиатура для выбора даты: 6 ближайших дней, 2 ряда по 3.
        """
        options = self._build_slot_options()
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

    async def _buttons_time_slots(self, date_str: str) -> List[dict]:
        """
        Клавиатура для выбора времени на указанную дату.
        9 слотов, 3 ряда по 3. Для занятых слотов текст 'ЗАНЯТО'.
        payload слота: slot_time:<date>:<start>-<end>
        """
        booked = await self._get_booked_slots_for_date(date_str)

        buttons: List[dict] = []
        for start, end in TIME_SLOTS:
            payload = f"slot_time:{date_str}:{start}-{end}"
            if payload in booked:
                text = "ЗАНЯТО"
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

    # ---------- Основная логика по тексту ----------

    async def handle_message(self, user_id: int, text: str) -> Tuple[str, Optional[List[dict]]]:
        """
        Обработка обычных текстовых сообщений (message_created).
        Возвращает (text, attachments) для отправки через /messages.
        """
        text_clean = text.strip()
        text_lower = text_clean.lower()

        # Команды отмены
        if text_lower in ("/cancel", "отмена", "стоп"):
            self._sessions.pop(user_id, None)
            return "Ок, заявку отменил. Чтобы начать заново, напиши /start.", None

        # Команда старта / новая заявка
        if text_lower in ("/start", "новая заявка", "заявка"):
            self._sessions[user_id] = DialogContext(state=DialogState.SERVICE)
            return (
                "Привет! Давай оформим новую заявку. Напиши, пожалуйста, какая услуга нужна.",
                None,
            )

        ctx = self._get_ctx(user_id)

        # Первый шаг: услуга
        if ctx.state == DialogState.SERVICE:
            ctx.service = text_clean
            ctx.state = DialogState.ADDRESS_MODE
            return (
                "Записал услугу.\n"
                "Где выполнить услугу?\n"
                "— Нажми «Мастерская», если привезёшь сам\n"
                "— Нажми «Ввести адрес», чтобы ввести адрес вручную\n"
                "Или просто отправь адрес текстом.",
                self._buttons_address_mode(),
            )

        # Если пользователь в ADDRESS_MODE и ввёл текст руками — считаем это адресом
        if ctx.state == DialogState.ADDRESS_MODE:
            ctx.address = text_clean
            ctx.state = DialogState.ADDRESS_DETAILS
            return (
                "Адрес записал.\n"
                "Уточни, пожалуйста, квартиру и подъезд.\n"
                "Если это частный дом, нажми «Частный дом» или напиши эти слова.",
                self._buttons_private_house(),
            )

        # Ввод адреса (если до этого нажал «Ввести адрес», а теперь пишет текст)
        if ctx.state == DialogState.ADDRESS:
            ctx.address = text_clean
            ctx.state = DialogState.ADDRESS_DETAILS
            return (
                "Адрес записал.\n"
                "Уточни, пожалуйста, квартиру и подъезд.\n"
                "Если это частный дом, нажми «Частный дом» или напиши эти слова.",
                self._buttons_private_house(),
            )

        # Уточнение по адресу: кв/подъезд (текстом, если не нажал кнопку)
        if ctx.state == DialogState.ADDRESS_DETAILS:
            if text_clean == "Частный дом":
                ctx.address_details = None
            else:
                ctx.address_details = text_clean
            ctx.state = DialogState.DESCRIPTION
            return (
                "Принял. Теперь опиши, пожалуйста, что нужно сделать (детально).",
                None,
            )

        # Описание → выбор даты
        if ctx.state == DialogState.DESCRIPTION:
            ctx.description = text_clean
            ctx.state = DialogState.SLOT
            return (
                "Принял описание. Когда удобно выполнить услугу?\n"
                "Можешь выбрать один из ближайших дней ниже или написать дату и время текстом.",
                self._buttons_slot_dates(),
            )

        # Текстовый ввод слота (дата/время) как фоллбек — минуя кнопки
        if ctx.state in (DialogState.SLOT, DialogState.SLOT_TIME):
            ctx.date = None
            ctx.slot = text_clean
            ctx.state = DialogState.NAME
            return "Ок. Как к тебе обращаться?", None

        if ctx.state == DialogState.NAME:
            ctx.name = text_clean
            ctx.state = DialogState.PHONE
            return (
                "Спасибо. Оставь, пожалуйста, номер телефона для связи (мобильный).",
                None,
            )

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
            reply = "Спасибо, заявку собрал. Отправляю мастеру, скоро свяжемся."

            await self._send_application_to_channel(user_id, ctx)
            self._sessions.pop(user_id, None)
            return reply, None

        # Фоллбек
        ctx.state = DialogState.SERVICE
        return (
            "Привет! Давай оформим заявку. Напиши, пожалуйста, какая услуга нужна.",
            None,
        )

    # ---------- Логика по callback (payload) ----------

    async def handle_callback(self, user_id: int, payload: str) -> Tuple[str, Optional[List[dict]]]:
        """
        Обработка нажатий на callback-кнопки (message_callback).
        payload — строка вида:
        - 'address_mode:workshop'
        - 'address_details:private_house'
        - 'slot:YYYY-MM-DD'
        - 'slot_time:YYYY-MM-DD:09:00-10:00'
        """
        ctx = self._get_ctx(user_id)

        # адрес: мастерская / ввод адреса
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
            return (
                "Хорошо, введи, пожалуйста, полный адрес (улица, дом, город).",
                None,
            )

        if payload == "address_details:private_house" and ctx.state == DialogState.ADDRESS_DETAILS:
            ctx.address_details = None
            ctx.state = DialogState.DESCRIPTION
            return (
                "Принял. Теперь опиши, пожалуйста, что нужно сделать (детально).",
                None,
            )

        # выбор даты: slot:YYYY-MM-DD
        if payload.startswith("slot:") and ctx.state == DialogState.SLOT:
            date_str = payload.split(":", 1)[1]  # '2026-05-15'
            ctx.date = self._format_pretty_date(date_str)
            ctx.slot = None
            ctx.state = DialogState.SLOT_TIME

            return (
                f"Выбери удобное время для {ctx.date}:",
                await self._buttons_time_slots(date_str),
            )

        # выбор времени: slot_time:YYYY-MM-DD:09:00-10:00
        if payload.startswith("slot_time:") and ctx.state == DialogState.SLOT_TIME:
            _, rest = payload.split(":", 1)
            # rest: '2026-05-15:09:00-10:00'
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

            # ctx.date уже хранит красивую дату
            ctx.slot = time_part  # "09:00-10:00"
            ctx.state = DialogState.NAME
            return "Ок. Как к тебе обращаться?", None

        # Если callback не соответствует текущему состоянию
        return (
            "Команда уже не актуальна. Напиши, пожалуйста, текстом, что хочешь сделать.",
            None,
        )

    # ---------- Отправка заявки в чат ----------

    async def _send_application_to_channel(self, user_id: int, ctx: DialogContext) -> None:
        lines = [
            "📝 Новая заявка",
            f"👤 Пользователь ID: {user_id}",
            f"🔧 Услуга: {ctx.service or '—'}",
        ]

        # Адрес / мастерская
        if ctx.address == "Мастерская":
            lines.append("🏭 Место выполнения: мастерская")
        elif ctx.address:
            lines.append(f"📍 Адрес: {ctx.address}")
        else:
            lines.append("📍 Адрес: не указан")

        if ctx.address_details:
            lines.append(f"📌 Уточнение по адресу: {ctx.address_details}")

        # Дата и время
        if ctx.date:
            lines.append(f"📅 Дата: {ctx.date}")
        if ctx.slot:
            lines.append(f"⏰ Время/слот: {ctx.slot}")

        # Описание и контакты
        lines.append(f"📄 Описание: {ctx.description or '—'}")
        lines.append(f"🙋‍♂️ Имя: {ctx.name or '—'}")
        lines.append(f"📞 Телефон: {ctx.phone or '—'}")

        text = "\n".join(lines)

        client = MaxClient()
        await client.send_text_to_chat(chat_id=MAX_APPLICATIONS_CHAT_ID, text=text)
        await client.close()


dialog_service = DialogService()