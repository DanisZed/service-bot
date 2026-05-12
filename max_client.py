import os
from typing import Optional

import httpx

MAX_API_BASE_URL = "https://platform-api.max.ru"

MAX_BOT_TOKEN = os.getenv("MAX_BOT_TOKEN")
MAX_APPLICATIONS_CHAT_ID = int(os.getenv("MAX_APPLICATIONS_CHAT_ID", "-74626173921476"))


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

    async def send_text_to_user(self, user_id: int, text: str) -> dict:
        params = {"user_id": str(user_id)}
        payload = {"text": text}
        resp = await self.client.post("/messages", params=params, json=payload)
        resp.raise_for_status()
        return resp.json()

    async def send_text_to_chat(self, chat_id: int, text: str) -> dict:
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