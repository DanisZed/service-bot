# app/api/max_webhook.py
import logging

from fastapi import APIRouter, Request, HTTPException, BackgroundTasks

from max_client import MaxClient
from app.services.dialog_service import dialog_service

router = APIRouter()

logger = logging.getLogger(__name__)

MAX_WEBHOOK_SECRET = "danis_super_secret_key_1"


async def handle_message_created(event: dict):
    message = event.get("message", {})
    sender = message.get("sender", {})
    body = message.get("body", {})

    user_id = sender.get("user_id")
    text = body.get("text", "")

    if not user_id:
        return

    reply_text, attachments = await dialog_service.handle_message(
        user_id=user_id,
        text=text,
    )

    client = MaxClient()
    await client.send_text_to_user(
        user_id=user_id,
        text=reply_text,
        attachments=attachments,
    )
    await client.close()


async def handle_message_callback(event: dict):
    """
    Обработка нажатия на callback-кнопку (update_type == 'message_callback').

    Формат из твоего лога:
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
    callback = event.get("callback", {}) or {}
    user = callback.get("user", {}) or {}

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
    message: dict = {"text": reply_text}
    if attachments:
        message["attachments"] = attachments

    await client.answer_callback(
        callback_id=callback_id,
        message=message,
        notification=None,
    )
    await client.close()


@router.post("/max/webhook")
async def max_webhook(request: Request, background_tasks: BackgroundTasks):
    body = await request.json()
    logger.info("MAX WEBHOOK BODY: %s", body)

    # Если у тебя есть проверка секрета — можно тут добавить
    # например, по header'у X-Hub-Signature или параметру
    # я оставляю MAX_WEBHOOK_SECRET неиспользованным, как у тебя сейчас.

    # У тебя приходит одиночный объект с полем update_type, без массива updates.
    update_type = body.get("update_type")

    if update_type == "message_created":
        background_tasks.add_task(handle_message_created, body)
    elif update_type == "message_callback":
        background_tasks.add_task(handle_message_callback, body)
    else:
        # игнорируем bot_started и прочие
        logger.debug("Ignored update_type: %s", update_type)

    return {"success": True}