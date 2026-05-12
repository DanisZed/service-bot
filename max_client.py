import os
import logging
from typing import Optional, List

import httpx

logger = logging.getLogger(__name__)

MAX_API_BASE_URL = "https://platform-api.max.ru"

MAX_BOT_TOKEN = os.getenv("MAX_BOT_TOKEN")
MAX_APPLICATIONS_CHAT_ID = int(os.getenv("MAX_APPLICATIONS_CHAT_ID", "-74638917986500"))


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
            timeout=20.0,  # увеличенный таймаут
        )

    async def send_text_to_user(
        self,
        user_id: int,
        text: str,
        attachments: Optional[List[dict]] = None,
    ) -> dict:
        params = {"user_id": str(user_id)}
        payload: dict = {"text": text}
        if attachments:
            payload["attachments"] = attachments

        try:
            resp = await self.client.post("/messages", params=params, json=payload)
        except httpx.ConnectTimeout:
            logger.error("MAX API ConnectTimeout (user) user_id=%s", user_id)
            return {}
        except httpx.ReadTimeout:
            logger.error("MAX API ReadTimeout (user) user_id=%s", user_id)
            return {}
        except httpx.NetworkError as e:
            logger.error("MAX API NetworkError (user) user_id=%s: %s", user_id, e)
            return {}

        if resp.status_code >= 400:
            try:
                logger.error("MAX API error (user): %s", resp.json())
            except Exception:
                logger.error("MAX API error (user): %s", resp.text)

        resp.raise_for_status()
        return resp.json()

    async def send_text_to_chat(
        self,
        chat_id: int,
        text: str,
        attachments: Optional[List[dict]] = None,
    ) -> dict:
        params = {"chat_id": str(chat_id)}
        payload: dict = {"text": text}
        if attachments:
            payload["attachments"] = attachments

        try:
            resp = await self.client.post("/messages", params=params, json=payload)
        except httpx.ConnectTimeout:
            logger.error("MAX API ConnectTimeout (chat) chat_id=%s", chat_id)
            return {}
        except httpx.ReadTimeout:
            logger.error("MAX API ReadTimeout (chat) chat_id=%s", chat_id)
            return {}
        except httpx.NetworkError as e:
            logger.error("MAX API NetworkError (chat) chat_id=%s: %s", chat_id, e)
            return {}

        if resp.status_code >= 400:
            try:
                logger.error("MAX API error (chat): %s", resp.json())
            except Exception:
                logger.error("MAX API error (chat): %s", resp.text)

        resp.raise_for_status()
        return resp.json()

    async def answer_callback(
        self,
        callback_id: str,
        message: Optional[dict] = None,
        notification: Optional[str] = None,
    ) -> dict:
        """
        POST /answers?callback_id=...
        Ответ на нажатие callback-кнопки.
        """
        params = {"callback_id": callback_id}
        payload: dict = {}
        if message is not None:
            payload["message"] = message
        if notification is not None:
            payload["notification"] = notification

        try:
            resp = await self.client.post("/answers", params=params, json=payload)
        except httpx.ConnectTimeout:
            logger.error("MAX API ConnectTimeout (answer_callback) callback_id=%s", callback_id)
            return {}
        except httpx.ReadTimeout:
            logger.error("MAX API ReadTimeout (answer_callback) callback_id=%s", callback_id)
            return {}
        except httpx.NetworkError as e:
            logger.error("MAX API NetworkError (answer_callback) callback_id=%s: %s", callback_id, e)
            return {}

        if resp.status_code >= 400:
            try:
                logger.error("MAX API error (answer_callback): %s", resp.json())
            except Exception:
                logger.error("MAX API error (answer_callback): %s", resp.text)

        resp.raise_for_status()
        return resp.json()

    async def close(self):
        await self.client.aclose()