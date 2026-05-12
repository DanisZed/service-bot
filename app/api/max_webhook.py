from fastapi import APIRouter, Request, HTTPException, BackgroundTasks

from max_client import MaxClient
from app.services.dialog_service import dialog_service

router = APIRouter()

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
    Ориентируемся на структуру Update из доки MAX:
    updates[i].callback.sender.user_id
    updates[i].callback.callback_id
    updates[i].callback.payload
    """
    callback = event.get("callback", {})
    sender = callback.get("sender", {}) or {}
    user_id = sender.get("user_id")
    callback_id = callback.get("callback_id")
    payload = callback.get("payload")

    if not user_id or not callback_id or payload is None:
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
    # если у тебя есть проверка секрета, оставь её
    body = await request.json()

    # По доке Update - массив updates. Но некоторые интеграции шлют один update.
    # Ориентируемся на то, что есть в твоём боте.
    updates = body.get("updates") or []
    if not updates and "update_type" in body:
        # fallback: одиночный update без массива
        updates = [body]

    for event in updates:
        update_type = event.get("update_type")

        if update_type == "message_created":
            background_tasks.add_task(handle_message_created, event)
        elif update_type == "message_callback":
            background_tasks.add_task(handle_message_callback, event)
        else:
            # игнорируем другие типы (bot_started и т.п.)
            continue

    return {"success": True}