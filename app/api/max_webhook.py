# app/api/max_webhook.py
import logging
from typing import Any, Dict

from fastapi import APIRouter, Request, BackgroundTasks

from max_client import MaxClient
from app.services.dialog_service import dialog_service
from app.services.max_commands import handle_command  # обработка /panel и др.
from app.db.models import Master
from app.db.session import AsyncSessionLocal
from sqlalchemy import select

router = APIRouter()
logger = logging.getLogger(__name__)

MAX_WEBHOOK_SECRET = "danis_super_secret_key_1"


# ========== СОХРАНЯЕМ АВАТАР ==========
    user_data = event.get("user") or {}
    avatar_url = user_data.get("full_avatar_url") or user_data.get("avatar_url")
    
    logger.info(f"AVATAR DEBUG: user_id={user_id}, avatar_url={avatar_url}, user_data={user_data}")
    
    if avatar_url:
        logger.info(f"AVATAR DEBUG: Найден аватар для user_id={user_id}, сохраняем...")
        try:
            async with AsyncSessionLocal() as session:
                result = await session.execute(
                    select(Master).where(Master.max_user_id == user_id)
                )
                master = result.scalar_one_or_none()
                logger.info(f"AVATAR DEBUG: Мастер найден: {master is not None}")
                
                if master:
                    logger.info(f"AVATAR DEBUG: Текущий avatar_url={master.avatar_url}, новый={avatar_url}")
                    if master.avatar_url != avatar_url:
                        master.avatar_url = avatar_url
                        await session.commit()
                        logger.info(f"AVATAR DEBUG: Аватар успешно сохранён для user_id={user_id}")
                    else:
                        logger.info(f"AVATAR DEBUG: Аватар не изменился, пропускаем")
                else:
                    logger.warning(f"AVATAR DEBUG: Мастер с user_id={user_id} не найден")
        except Exception as e:
            logger.error(f"AVATAR DEBUG: Ошибка при сохранении аватара: {e}")
    else:
        logger.info(f"AVATAR DEBUG: avatar_url не найден в user_data для user_id={user_id}")

    reply_text: Optional[str] = None
    attachments: Optional[List[dict]] = None

    # 0) Диплинк start=panel -> /panel
    if isinstance(payload, str) and payload.strip().lower() == "panel":
        reply_text, attachments = await handle_command(user_id, "/panel")

    # НОВОЕ: диплинк start=activate -> показать кнопку "Начать"
    if reply_text is None and isinstance(payload, str) and payload.strip().lower() == "activate":
        reply_text = (
            "✅ Регистрация завершена.\n\n"
            "Теперь вы можете создавать заявки через этого бота.\n"
            "Нажмите кнопку ниже, чтобы начать оформление первой заявки."
        )
        attachments = [
            {
                "type": "inline_keyboard",
                "payload": {
                    "buttons": [
                        [
                            {
                                "type": "callback",
                                "text": "🚀 Начать",
                                "payload": "activate_start",
                                "intent": "default",
                            }
                        ]
                    ]
                },
            }
        ]

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

    # НОВОЕ: обработка кнопки "Начать" после диплинка activate
    if payload == "activate_start":
        # эмулируем /start → запускаем диалог
        reply_text, attachments = await dialog_service.start_or_reset(user_id)

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

    if isinstance(payload, str) and payload.strip().lower() == "panel":
        # уже было
        reply_text, attachments = await handle_command(user_id, "/panel")

    elif isinstance(payload, str) and payload.strip().lower() == "activate":
        # НОВОЕ: диплинк ?start=activate
        # Показываем кнопку "Начать", которая эмулирует /start
        reply_text = (
            "Добро пожаловать в Техник Сервис CRM.\n"
            "Нажмите кнопку ниже, чтобы начать оформление заявки."
        )

        # одна кнопка "Начать" с callback payload "activate_start"
        attachments = [
            {
                "type": "inline_keyboard",
                "payload": {
                    "buttons": [
                        [
                            {
                                "type": "callback",
                                "text": "Начать",
                                "payload": "activate_start",
                                "intent": "default",
                            }
                        ]
                    ]
                },
            }
        ]

    else:
        reply_text = (
            "Привет! Я бот Техник Сервис CRM.\n"
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

