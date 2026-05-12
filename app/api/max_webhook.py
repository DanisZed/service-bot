from fastapi import APIRouter, Request, HTTPException, BackgroundTasks

from max_client import MaxClient

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

    client = MaxClient()
    reply_text = f"Привет! Я бот заявок. Ты написал: {text}"
    await client.send_text_to_user(user_id=user_id, text=reply_text)
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