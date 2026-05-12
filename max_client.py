import os
from typing import Optional

import httpx

MAX_API_BASE_URL = "https://platform-api.max.ru"

# Токен бота берём из переменной окружения
MAX_BOT_TOKEN = os.getenv("MAX_BOT_TOKEN")


class MaxClient:
    def __init__(self, token: Optional[str] = None):
        self.token = token or MAX_BOT_TOKEN
        if not self.token:
            raise ValueError("MAX bot token is not set (env MAX_BOT_TOKEN)")

        self.client = httpx.AsyncClient(
            base_url=MAX_API_BASE_URL,
            headers={
                "Authorization": self.token,
                "Content-Type": "application/json",
            },
            timeout=10.0,
        )

    async def send_text(self, chat_id: int, text: str) -> dict:
        payload = {
            "recipient": {
                "chat_id": chat_id,
            },
            "message": {
                "text": text,
            },
        }
        resp = await self.client.post("/messages", json=payload)
        resp.raise_for_status()
        return resp.json()

    async def close(self):
        await self.client.aclose()