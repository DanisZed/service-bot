# app/api/max_webhook.py
import logging
from typing import Any, Dict

from fastapi import APIRouter, Request, BackgroundTasks

from max_client import MaxClient
from app.services.dialog_service import dialog_service
from app.services.max_commands import handle_command  # обработка /panel и др.
from app.db.models import Master
from sqlalchemy import select

router = APIRouter()
logger = logging.getLogger(__name__)

MAX_WEBHOOK_SECRET = "danis_super_secret_key_1"


async def handle_message_created(event: Dict[str, Any]) -> None:
    message = event.get("message") or {}
    sender = message.get("sender") or {}
    body = message.get("body") or {}

    # Временно логируем всё сообщение целиком
    logger.info("RAW MAX MESSAGE: %r", message)

    user_id = sender.get("user_id")
    text = body.get("text", "")
    # пробуем достать payload/start-параметр, если он есть в событии
    # (если у тебя другое поле — здесь поправим)
    payload = body.get("payload") or body.get("start_param")

    logger.info(
        "MY_DEBUG: message from user_id=%s body=%s payload=%s",
        user_id,
        text,
        payload,
    )

    if not user_id:
        logger.warning("message_created without user_id: %s", event)
        return

    reply_text = None
    attachments = None

    # 0) Обработка диплинка start=panel:
    # если пользователь открыл бота по ссылке
    # https://max.ru/id027308840424_bot?start=panel
    # и MAX прокинул сюда payload="panel" — считаем это как команду /panel.
    if isinstance(payload, str) and payload.strip().lower() == "panel":
        # имитируем, что пользователь ввёл /panel
        reply_text, attachments = await handle_command(user_id, "/panel")

    # 1) Если диплинк не сработал или payload другой — пробуем обычную команду
    if reply_text is None:
        reply_text, attachments = await handle_command(user_id, text)

    # 2) Если команда не распознана — идём в диалоговый сервис
    if reply_text is None:
        lower = text.strip().lower()
        if lower in ("/start", "новая заявка", "заявка"):
            reply_text, attachments = await dialog_service.start_or_reset(user_id)
        else:
            reply_text, attachments = await dialog_service.handle_message(
                user_id, text
            )

    client = MaxClient()
    try:
        await client.send_text_to_user(
            user_id=user_id,
            text=reply_text,
            attachments=attachments,
        )
    finally:
        await client.close()


async def handle_message_callback(event: Dict[str, Any]) -> None:
    callback = event.get("callback") or {}
    user = callback.get("user") or {}
    payload = callback.get("payload")

    user_id = user.get("user_id")
    callback_id = callback.get("callback_id")

    if not user_id or not callback_id or payload is None:
        logger.warning("Invalid message_callback event: %s", event)
        return

    reply_text, attachments = await dialog_service.handle_callback(
        user_id=user_id,
        payload=payload,
    )

    client = MaxClient()
    try:
        message_out: Dict[str, Any] = {"text": reply_text}
        message_out["attachments"] = [] if attachments is None else attachments

        await client.answer_callback(
            callback_id=callback_id,
            message=message_out,
            notification=None,
        )
    finally:
        await client.close()


@router.post("/max/webhook")
async def max_webhook(
    request: Request, background_tasks: BackgroundTasks
) -> Dict[str, Any]:
  body = await request.json()
  logger.info("MAX WEBHOOK BODY: %s", body)

  update_type = body.get("update_type")

  if update_type == "message_created":
      background_tasks.add_task(handle_message_created, body)
  elif update_type == "message_callback":
      background_tasks.add_task(handle_message_callback, body)
  elif update_type == "bot_started":
      background_tasks.add_task(handle_bot_started, body)
  else:
      logger.debug("Ignored update_type: %s", update_type)

  return {"success": True}

# app/api/max_webhook.py

async def handle_bot_started(event: Dict[str, Any]) -> None:
    user = event.get("user") or {}
    user_id = user.get("user_id")
    payload = event.get("payload")

    logger.info(
        "MAX BOT_STARTED: user_id=%s payload=%r event=%r",
        user_id,
        payload,
        event,
    )

    if not user_id:
        logger.warning("bot_started without user_id: %s", event)
        return

    reply_text = None
    attachments = None

    # ========== ОБРАБОТКА ЗАВЕРШЕНИЯ РЕГИСТРАЦИИ ==========
    if isinstance(payload, str) and payload.startswith("complete_"):
        master_id = payload.replace("complete_", "")
        
        # Проверяем, что мастер активирован
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(Master).where(Master.master_id == master_id, Master.is_active == 1)
            )
            master = result.scalar_one_or_none()
        
        if not master:
            reply_text = "❌ Ошибка: регистрация не завершена. Попробуйте снова."
            attachments = None
        else:
            # Формируем сообщение об успешной регистрации с кнопкой "Новая заявка"
            kb = [{
                "type": "inline_keyboard",
                "payload": {
                    "buttons": [[{
                        "type": "callback",
                        "text": "📝 Новая заявка",
                        "payload": "menu:new_request",
                        "intent": "default",
                    }]]
                }
            }]
            
            role_text = "Администратор" if master.is_admin else "Мастер"
            name_text = master.name or master.service_name or ""
            
            reply_text = (
                f"🎉 **Регистрация успешно завершена!**\n\n"
                f"👤 Роль: {role_text}\n"
                f"📛 {name_text}\n"
                f"🆔 ID мастера: `{master.master_id}`\n\n"
                f"Теперь вы можете создавать заявки.\n\n"
                f"Нажмите «Новая заявка», чтобы начать."
            )
            attachments = kb
        
        # Отправляем сообщение пользователю
        client = MaxClient()
        try:
            await client.send_text_to_user(
                user_id=user_id,
                text=reply_text,
                attachments=attachments,
            )
        finally:
            await client.close()
        return

    # ========== ОБРАБОТКА ПАНЕЛИ ==========
    if isinstance(payload, str) and payload.strip().lower() == "panel":
        reply_text, attachments = await handle_command(user_id, "/panel")
    else:
        # обычное приветствие без panel
        reply_text = (
            "Авторизация в системе РБТ | CRM.\n"
            "Чтобы открыть панель мастера, отправьте команду /panel."
        )
        attachments = None

    client = MaxClient()
    try:
        await client.send_text_to_user(
            user_id=user_id,
            text=reply_text,
            attachments=attachments,
        )
    finally:
        await client.close()