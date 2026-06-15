import os
import logging
import asyncio
from pathlib import Path
from typing import Optional, List, Dict, Any
import httpx
from dotenv import load_dotenv


logger = logging.getLogger(__name__)


BASE_DIR = Path(__file__).resolve().parent
env_path = BASE_DIR / ".env"
if env_path.exists():
    load_dotenv(env_path)


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


        self.base_url = MAX_API_BASE_URL
        auth_header = self.token
        timeout = httpx.Timeout(
            connect=connect_timeout,
            read=read_timeout,
            write=write_timeout,
            pool=pool_timeout,
        )
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
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
        last_exc = None
        for attempt in range(self.retries + 1):
            try:
                resp = await self.client.request(method, url, params=params, json=json)
                if resp.status_code >= 400:
                    try:
                        body = resp.json()
                    except:
                        body = resp.text
                    logger.error("MAX API error (%s): status=%s body=%s", context or url, resp.status_code, body)
                    return {}
                return resp.json()
            except httpx.ReadTimeout as e:
                last_exc = e
                logger.error("MAX API ReadTimeout (%s) attempt=%s", context or url, attempt+1)
                if attempt == self.retries:
                    break
            except httpx.ConnectTimeout as e:
                last_exc = e
                logger.error("MAX API ConnectTimeout (%s)", context or url)
                break
            except Exception as e:
                last_exc = e
                logger.exception("MAX API unexpected error (%s)", context or url)
                break
        if last_exc:
            logger.debug("MAX API last exception (%s): %r", context or url, last_exc)
        return {}


    async def send_text_to_user(
        self, user_id: int, text: str, attachments: Optional[List[dict]] = None
    ) -> Dict[str, Any]:
        params = {"user_id": str(user_id)}
        payload = {"text": text}
        if attachments:
            payload["attachments"] = attachments
        resp = await self._request("POST", "/messages", params=params, json=payload, context=f"user user_id={user_id}")
        print("### MAX send_text_to_user resp=", resp)
        return resp


    async def send_text_to_chat(
        self, chat_id: int, text: str, attachments: Optional[List[dict]] = None
    ) -> Dict[str, Any]:
        params = {"chat_id": str(chat_id)}
        payload = {"text": text}
        if attachments:
            payload["attachments"] = attachments
        return await self._request("POST", "/messages", params=params, json=payload, context=f"chat chat_id={chat_id}")


    async def answer_callback(
        self, callback_id: str, message: Optional[dict] = None, notification: Optional[str] = None
    ) -> Dict[str, Any]:
        params = {"callback_id": callback_id}
        payload = {}
        if message is not None:
            payload["message"] = message
        if notification is not None:
            payload["notification"] = notification
        return await self._request("POST", "/answers", params=params, json=payload, context=f"answer_callback callback_id={callback_id}")


    async def send_file(
        self,
        user_id: int,
        file_bytes: bytes,
        filename: str,
        caption: Optional[str] = None,
        max_retries: int = 5,
        initial_delay: float = 3.0,
        base_delay: float = 5.0,
    ) -> Dict[str, Any]:
        """
        Отправляет файл пользователю с повторными попытками и правильной паузой.
        Согласно документации MAX: после загрузки файла сделать паузу перед отправкой [web:1].
        """
        # Шаг 1: Получаем URL для загрузки
        upload_resp = await self._request(
            "POST", "/uploads", params={"type": "file"}, context="get_upload_url"
        )
        if not upload_resp or "url" not in upload_resp:
            raise Exception("Не удалось получить URL для загрузки")
        upload_url = upload_resp["url"]


        # Шаг 2: Загружаем файл
        async with httpx.AsyncClient() as client:
            files = {"data": (filename, file_bytes, "application/pdf")}
            resp = await client.post(upload_url, files=files)
            resp.raise_for_status()
            upload_data = resp.json()


        # Получаем токен вложения
        attachment_token = upload_data.get("token")
        if not attachment_token:
            raise Exception("Не удалось получить токен вложения после загрузки")


        # Шаг 3: ПАУЗА после загрузки перед отправкой (согласно документации MAX)
        await asyncio.sleep(initial_delay)
        logger.info(f"Пауза {initial_delay}с после загрузки файла, начинаю отправку")


        # Шаг 4: Отправляем сообщение с вложением с повторными попытками
        attachments = [{"type": "file", "payload": {"token": attachment_token}}]


        for attempt in range(max_retries):
            try:
                if caption:
                    resp = await self.send_text_to_user(user_id, caption, attachments)
                else:
                    resp = await self.send_text_to_user(user_id, "", attachments)
                
                # Проверяем ошибку в ответе (если MAX вернул ошибку с кодом)
                if resp and isinstance(resp, dict) and "code" in resp:
                    if resp["code"] == "attachment.not.ready":
                        logger.warning(f"Попытка {attempt+1}: attachment.not.ready, повторяю через {base_delay * (2 ** attempt)}с")
                        if attempt == max_retries - 1:
                            raise Exception("attachment.not.ready после всех попыток")
                        # Экспоненциальная задержка: 5, 10, 20, 40 сек.
                        delay = base_delay * (2 ** attempt)
                        await asyncio.sleep(delay)
                        continue
                
                # Если отправка успешна - возвращаем ответ
                return resp
                
            except Exception as e:
                logger.warning(f"Попытка {attempt+1} отправки файла не удалась: {e}")
                if attempt == max_retries - 1:
                    raise
                # Ждём с увеличивающейся задержкой
                delay = base_delay * (2 ** attempt)
                await asyncio.sleep(delay)


        return {}


    async def close(self) -> None:
        await self.client.aclose()



class MaxOrderBotClient(MaxClient):
    def __init__(self, token: Optional[str] = None, **kwargs):
        order_token = token or os.getenv("MAX_ORDER_BOT_TOKEN")
        if not order_token:
            raise ValueError("MAX_ORDER_BOT_TOKEN is not set")
        super().__init__(token=order_token, **kwargs)