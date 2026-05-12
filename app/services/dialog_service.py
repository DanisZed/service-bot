# app/services/dialog_service.py
from dataclasses import dataclass, field
from typing import Dict, Optional

from max_client import MaxClient, MAX_APPLICATIONS_CHAT_ID


class DialogState:
    IDLE = "idle"
    SERVICE = "service"
    ADDRESS = "address"
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

    async def handle_message(self, user_id: int, text: str) -> str:
        ctx = self._get_ctx(user_id)

        if text.lower() in ("стоп", "отмена", "cancel"):
            self._sessions.pop(user_id, None)
            return "Ок, заявку отменил. Если нужно — напиши ещё раз."

        if ctx.state == DialogState.SERVICE:
            ctx.service = text.strip()
            ctx.state = DialogState.ADDRESS
            return "Записал услугу. Укажи, пожалуйста, адрес выполнения."

        if ctx.state == DialogState.ADDRESS:
            ctx.address = text.strip()
            ctx.state = DialogState.DESCRIPTION
            return "Адрес есть. Опиши, что нужно сделать (детально)."

        if ctx.state == DialogState.DESCRIPTION:
            ctx.description = text.strip()
            ctx.state = DialogState.SLOT
            return "Принял описание. Когда удобно выполнить услугу? (дата/диапазон времени)"

        if ctx.state == DialogState.SLOT:
            ctx.slot = text.strip()
            ctx.state = DialogState.NAME
            return "Ок. Как к тебе обращаться?"

        if ctx.state == DialogState.NAME:
            ctx.name = text.strip()
            ctx.state = DialogState.PHONE
            return "Спасибо. Оставь, пожалуйста, номер телефона для связи."

        if ctx.state == DialogState.PHONE:
            ctx.phone = text.strip()
            ctx.state = DialogState.CONFIRMED
            reply = "Спасибо, заявку собрал. Отправляю мастеру, скоро свяжемся."

            await self._send_application_to_channel(user_id, ctx)
            self._sessions.pop(user_id, None)
            return reply

        ctx.state = DialogState.SERVICE
        return "Привет! Давай оформим заявку. Опиши, пожалуйста, услугу, которая нужна."

    async def _send_application_to_channel(self, user_id: int, ctx: DialogContext) -> None:
        lines = [
            "📝 Новая заявка",
            f"👤 Пользователь ID: {user_id}",
            f"🔧 Услуга: {ctx.service}",
            f"📍 Адрес: {ctx.address}",
            f"📄 Описание: {ctx.description}",
            f"⏰ Время/слот: {ctx.slot}",
            f"🙋‍♂️ Имя: {ctx.name}",
            f"📞 Телефон: {ctx.phone}",
        ]
        text = "\n".join(lines)

        client = MaxClient()
        await client.send_text_to_chat(chat_id=MAX_APPLICATIONS_CHAT_ID, text=text)
        await client.close()


dialog_service = DialogService()