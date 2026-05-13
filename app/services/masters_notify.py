from typing import List

from app.db.session import AsyncSessionLocal
from app.db.models import ServiceRequest, Master
from max_client_second_bot import MaxClientSecondBot


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

        if req.address:
            lines.append(f"📍 Адрес: {req.address}")
        else:
            lines.append("📍 Адрес: не указан")

        if req.date_iso:
            lines.append(f"📅 Дата: {req.date_iso.strftime('%d.%m.%Y')}")
        if req.time_slot:
            lines.append(f"⏰ Время: {req.time_slot}")

        if req.client_name:
            lines.append(f"🙋‍♂️ Клиент: {req.client_name}")
        if req.client_phone:
            lines.append(f"📞 Телефон: {req.client_phone}")

        text = "\n".join(lines)

        client = MaxClientSecondBot()
        try:
            await client.send_text_to_user(
                user_id=master.max_user_id,
                text=text,
                attachments=None,
            )
        finally:
            await client.close()