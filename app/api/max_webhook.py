from fastapi import APIRouter, Request

router = APIRouter()


@router.post("/webhook")
async def max_webhook(request: Request):
    data = await request.json()
    # Здесь позже будет разбор событий MAX и диалоговая логика
    print("MAX webhook:", data)
    return {"ok": True}
