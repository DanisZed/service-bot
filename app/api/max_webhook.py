# app/api/max_webhook.py
import logging
from typing import Any, Dict

from fastapi import APIRouter, Request, BackgroundTasks

from app.integrations.max_client import MaxClient  # поправь путь, если файл лежит в другом месте
from app.services.dialog_service import dialog_service  # твой модуль диалогов

router = APIRouter()

logger = logging.getLogger(__name__)

MAX_WEBHOOK_SECRET = "danis_super_secret_key_1"


async def handle_message_created(event: Dict[str, Any]) -> None:
    """
    Обработка входящего сообщения от пользователя (update_type == 'message_created').

    Здесь мы:
      - достаём user_id и текст;
      - передаём их в dialog_service.handle_message;
      - получаем текст ответа и attachments для MAX;
      - отправляем ответ пользователю.
    """
    message = event.get("message") or {}
    sender = message.get("sender") or {}
    body = message.get("body") or {}

    user_id = sender.get("user_id")
    text = body.get("text", "")

    if not user_id:
        logger.warning("message_created without user_id: %s", event)
        return

    reply_text, attachments = await dialog_service.handle_message(
        user_id=user_id,
        text=text,
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
    """
    Обработка нажатия на callback-кнопку (update_type == 'message_callback').

    Формат из лога:
    {
      "callback": {
        "timestamp": ...,
        "callback_id": "...",
        "user": { "user_id": 40398020, ... },
        "payload": "address_mode:workshop"
      },
      "message": {...},
      "timestamp": ...,
      "user_locale": "ru",
      "update_type": "message_callback"
    }
    """
    callback = event.get("callback") or {}
    user = callback.get("user") or {}

    user_id = user.get("user_id")
    callback_id = callback.get("callback_id")
    payload = callback.get("payload")

    if not user_id or not callback_id or payload is None:
        logger.warning("Invalid message_callback event: %s", event)
        return

    reply_text, attachments = await dialog_service.handle_callback(
        user_id=user_id,
        payload=payload,
    )

    client = MaxClient()
    try:
        # Если attachments is None — очищаем клавиатуру (attachments=[]).
        # Если attachments не None — подставляем новую клавиатуру.
        message: Dict[str, Any] = {"text": reply_text}
        if attachments is None:
            message["attachments"] = []
        else:
            message["attachments"] = attachments

        await client.answer_callback(
            callback_id=callback_id,
            message=message,
            notification=None,
        )
    finally:
        await client.close()


@router.post("/max/webhook")
async def max_webhook(request: Request, background_tasks: BackgroundTasks) -> Dict[str, Any]:
    body = await request.json()
    logger.info("MAX WEBHOOK BODY: %s", body)

    update_type = body.get("update_type")

    if update_type == "message_created":
        background_tasks.add_task(handle_message_created, body)
    elif update_type == "message_callback":
        background_tasks.add_task(handle_message_callback, body)
    else:
        # игнорируем bot_started и прочие
        logger.debug("Ignored update_type: %s", update_type)

    return {"success": True}