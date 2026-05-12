from dataclasses import dataclass
from typing import Dict, Optional, List, Tuple

from max_client import MaxClient, MAX_APPLICATIONS_CHAT_ID


class DialogState:
    IDLE = "idle"
    SERVICE = "service"
    ADDRESS_MODE = "address_mode"        # выбор: мастерская / ввод адреса / сразу текстом
    ADDRESS = "address"                  # ввод адреса
    ADDRESS_DETAILS = "address_details"  # кв/подъезд
    DESCRIPTION = "description"
    SLOT = "slot"
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
    slot: Optional[str] = None
    name: Optional[str] = None
    phone: Optional[str] = None


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

    # ---------- Кнопки ----------

    def _inline_keyboard(self, buttons: List[dict]) -> List[dict]:
        return [
            {
                "type": "inline_keyboard",
                "payload": {
                    "buttons": buttons,
                },
            }
        ]

    def _buttons_address_mode(self) -> List[dict]:
        return self._inline_keyboard(
            [
                {"type": "message", "text": "Мастерская"},
                {"type": "message", "text": "Ввести адрес"},
            ]
        )

    def _buttons_private_house(self) -> List[dict]:
        return self._inline_keyboard(
            [
                {"type": "message", "text": "Частный дом"},
            ]
        )

    # ---------- Основная логика ----------

    async def handle_message(self, user_id: int, text: str) -> Tuple[str, Optional[List[dict]]]:
        """
        Возвращает (text, attachments), где attachments — массив объектов inline_keyboard для MAX.
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

        # Выбор режима адреса: мастерская или ручной ввод
        if ctx.state == DialogState.ADDRESS_MODE:
            if text_clean == "Мастерская":
                ctx.address = "Мастерская"
                ctx.address_details = None
                ctx.state = DialogState.DESCRIPTION
                return (
                    "Понял, работа в мастерской.\n"
                    "Опиши, пожалуйста, что нужно сделать (детально).",
                    None,
                )

            if text_clean == "Ввести адрес":
                ctx.state = DialogState.ADDRESS
                return (
                    "Хорошо, введи, пожалуйста, полный адрес (улица, дом, город).",
                    None,
                )

            # Если просто текст — считаем, что это адрес
            ctx.address = text_clean
            ctx.state = DialogState.ADDRESS_DETAILS
            return (
                "Адрес записал.\n"
                "Уточни, пожалуйста, квартиру и подъезд.\n"
                "Если это частный дом, нажми «Частный дом» или напиши эти слова.",
                self._buttons_private_house(),
            )

        # Ввод адреса (если выбрали «Ввести адрес»)
        if ctx.state == DialogState.ADDRESS:
            ctx.address = text_clean
            ctx.state = DialogState.ADDRESS_DETAILS
            return (
                "Адрес записал.\n"
                "Уточни, пожалуйста, квартиру и подъезд.\n"
                "Если это частный дом, нажми «Частный дом» или напиши эти слова.",
                self._buttons_private_house(),
            )

        # Уточнение по адресу: кв/подъезд или частный дом
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

        # Описание работ
        if ctx.state == DialogState.DESCRIPTION:
            ctx.description = text_clean
            ctx.state = DialogState.SLOT
            return (
                "Принял описание. Когда удобно выполнить услугу? Напиши дату и время или диапазон.",
                None,
            )

        # Время/слот
        if ctx.state == DialogState.SLOT:
            ctx.slot = text_clean
            ctx.state = DialogState.NAME
            return "Ок. Как к тебе обращаться?", None

        # Имя
        if ctx.state == DialogState.NAME:
            ctx.name = text_clean
            ctx.state = DialogState.PHONE
            return (
                "Спасибо. Оставь, пожалуйста, номер телефона для связи (мобильный).",
                None,
            )

        # Телефон с валидацией
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

        # Фоллбек — если состояние потеряли
        ctx.state = DialogState.SERVICE
        return (
            "Привет! Давай оформим заявку. Напиши, пожалуйста, какая услуга нужна.",
            None,
        )

    async def _send_application_to_channel(self, user_id: int, ctx: DialogContext) -> None:
        lines = [
            "📝 Новая заявка",
            f"👤 Пользователь ID: {user_id}",
            f"🔧 Услуга: {ctx.service}",
            f"📍 Адрес: {ctx.address}",
        ]

        if ctx.address_details:
            lines.append(f"📌 Уточнение: {ctx.address_details}")

        lines.extend(
            [
                f"📄 Описание: {ctx.description}",
                f"⏰ Время/слот: {ctx.slot}",
                f"🙋‍♂️ Имя: {ctx.name}",
                f"📞 Телефон: {ctx.phone}",
            ]
        )

        text = "\n".join(lines)

        client = MaxClient()
        await client.send_text_to_chat(chat_id=MAX_APPLICATIONS_CHAT_ID, text=text)
        await client.close()


dialog_service = DialogService()