import os
import logging
from typing import Optional, List, Dict, Any

import httpx

logger = logging.getLogger(__name__)

MAX_API_BASE_URL = "https://platform-api.max.ru"

MAX_BOT_TOKEN = os.getenv("MAX_BOT_TOKEN")
MAX_APPLICATIONS_CHAT_ID = int(os.getenv("MAX_APPLICATIONS_CHAT_ID", "-74638917986500"))


class MaxClient:
    def __init__(
        self,
        token: Optional[str] = None,
        *,
        connect_timeout: float = 3.0,
        read_timeout: float = 15.0,
        write_timeout: float = 10.0,
        pool_timeout: float = 5.0,
        retries: int = 1,
    ) -> None:
        self.token = token or MAX_BOT_TOKEN
        if not self.token:
            raise ValueError("MAX bot token is not set (env MAX_BOT_TOKEN)")

        # Если MAX требует Bearer — включи следующую строку,
        # и убедись, что MAX_BOT_TOKEN хранится без 'Bearer '.
        auth_header = self.token
        # auth_header = f"Bearer {self.token}"

        timeout = httpx.Timeout(
            connect=connect_timeout,
            read=read_timeout,
            write=write_timeout,
            pool=pool_timeout,
        )

        self.client = httpx.AsyncClient(
            base_url=MAX_API_BASE_URL,
            headers={
                "Authorization": auth_header,
                "Content-Type": "application/json",
            },
            timeout=timeout,
        )

        self.retries = retries

    async def _request(
        self,
        method: str,
        url: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
        context: str = "",
    ) -> Dict[str, Any]:
        """
        Общий helper для запросов к MAX API с retry и логированием.
        Возвращает {} при сетевых ошибках/таймаутах или при ошибках статуса.
        """
        last_exc: Optional[BaseException] = None

        for attempt in range(self.retries + 1):
            try:
                resp = await self.client.request(
                    method=method,
                    url=url,
                    params=params,
                    json=json,
                )

                if resp.status_code >= 400:
                    try:
                        body = resp.json()
                    except Exception:
                        body = resp.text

                    logger.error(
                        "MAX API error (%s): status=%s body=%s",
                        context or url,
                        resp.status_code,
                        body,
                    )
                    # Если нужно, можно не падать, а просто вернуть тело:
                    # return {"status_code": resp.status_code, "body": body}
                    return {}

                return resp.json()

            except httpx.ReadTimeout as e:
                last_exc = e
                logger.error(
                    "MAX API ReadTimeout (%s) attempt=%s",
                    context or url,
                    attempt + 1,
                )
                if attempt == self.retries:
                    break
            except httpx.ConnectTimeout as e:
                last_exc = e
                logger.error(
                    "MAX API ConnectTimeout (%s) attempt=%s",
                    context or url,
                    attempt + 1,
                )
                # Обычно при ConnectTimeout ретраи мало помогают, выходим сразу
                break
            except httpx.NetworkError as e:
                last_exc = e
                logger.error(
                    "MAX API NetworkError (%s): %s",
                    context or url,
                    e,
                )
                break
            except Exception as e:
                last_exc = e
                logger.exception(
                    "MAX API unexpected error (%s) attempt=%s",
                    context or url,
                    attempt + 1,
                )
                break

        if last_exc:
            logger.debug("MAX API last exception (%s): %r", context or url, last_exc)
        return {}

    async def send_text_to_user(
        self,
        user_id: int,
        text: str,
        attachments: Optional[List[dict]] = None,
    ) -> Dict[str, Any]:
        params = {"user_id": str(user_id)}
        payload: Dict[str, Any] = {"text": text}
        if attachments:
            payload["attachments"] = attachments

        return await self._request(
            "POST",
            "/messages",
            params=params,
            json=payload,
            context=f"user user_id={user_id}",
        )

    async def send_text_to_chat(
        self,
        chat_id: int,
        text: str,
        attachments: Optional[List[dict]] = None,
    ) -> Dict[str, Any]:
        params = {"chat_id": str(chat_id)}
        payload: Dict[str, Any] = {"text": text}
        if attachments:
            payload["attachments"] = attachments

        return await self._request(
            "POST",
            "/messages",
            params=params,
            json=payload,
            context=f"chat chat_id={chat_id}",
        )

    async def answer_callback(
        self,
        callback_id: str,
        message: Optional[dict] = None,
        notification: Optional[str] = None,
    ) -> Dict[str, Any]:
        params = {"callback_id": callback_id}
        payload: Dict[str, Any] = {}
        if message is not None:
            payload["message"] = message
        if notification is not None:
            payload["notification"] = notification

        return await self._request(
            "POST",
            "/answers",
            params=params,
            json=payload,
            context=f"answer_callback callback_id={callback_id}",
        )

    async def close(self) -> None:
        await self.client.aclose()