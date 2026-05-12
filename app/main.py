from fastapi import FastAPI
from app.api.max_webhook import router as max_router

app = FastAPI()


@app.get("/health")
async def health():
    return {"status": "ok"}


# Подключаем роуты MAX webhook
app.include_router(max_router)