from fastapi import APIRouter, Request, HTTPException, BackgroundTasks

from max_client import MaxClient

router = APIRouter()

MAX_WEBHOOK_SECRET = "danis_super_secret_key_1"  # тот же, что в подписке


async def handle_message_created(event: dict):
    message = event.get("message", {})
    recipient = message.get("recipient", {})
    body = message.get("body", {})

    chat_id = recipient.get("chat_id")
    text = body.get("text", "")

    if not chat_id:
        return

    client = MaxClient()
    reply_text = f"Привет! Я бот заявок. Ты написал: {text}"
    await client.send_text(chat_id=chat_id, text=reply_text)
    await client.close()


@router.post("/max/webhook")
async def max_webhook(request: Request, background_tasks: BackgroundTasks):
    secret = request.headers.get("X-Max-Bot-Api-Secret")
    if secret != MAX_WEBHOOK_SECRET:
        raise HTTPException(status_code=403, detail="Invalid secret")

    payload = await request.json()
    print("MAX webhook:", payload)

    update_type = payload.get("update_type")

    if update_type == "message_created":
        background_tasks.add_task(handle_message_created, payload)

    return {"ok": True}