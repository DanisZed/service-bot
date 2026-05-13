from typing import List, Optional
from datetime import datetime

from app.db.session import AsyncSessionLocal
from app.db.models import ServiceRequest, Master
from max_client_second_bot import MaxClientSecondBot

# импортируем диалоговый сервис, чтобы использовать его функции построения ссылок
from app.services.dialog_service import dialog_service  # у тебя в конце файла как раз dialog_service = UnifiedDialogService()


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

        # date_iso у тебя в модели может быть date/datetime/str — подстрои при необходимости
        if isinstance(req.date_iso, datetime):
            lines.append(f"📅 Дата: {req.date_iso.strftime('%d.%m.%Y')}")
            date_iso_str: Optional[str] = req.date_iso.date().isoformat()
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

        # --- строим ссылки, как в dialog_service._send_application_to_channel ---
        yandex_url = dialog_service._build_yandex_url(req.address)
        google_url = dialog_service._build_google_calendar_url(
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