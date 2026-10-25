import os
import logging
import asyncio
from pathlib import Path
from typing import Optional, List, Dict, Any

import httpx
from dotenv import load_dotenv


logger = logging.getLogger(__name__)


# Загружаем .env из папки, где лежит этот файл.
BASE_DIR = Path(__file__).resolve().parent
env_path = BASE_DIR / ".env"

if env_path.exists():
    load_dotenv(env_path)


# Базовый URL API MAX.
MAX_API_BASE_URL = "https://platform-api.max.ru"

# Токен основного бота.
MAX_BOT_TOKEN = os.getenv("MAX_BOT_TOKEN")

# Чат, куда отправляются заявки.
MAX_APPLICATIONS_CHAT_ID = int(
    os.getenv("MAX_APPLICATIONS_CHAT_ID", "-74638917986500")
)


class MaxClient:
    """
    HTTP-клиент для MAX Bot API.

    - держит одно переиспользуемое соединение;
    - передаёт токен в заголовке Authorization;
    - повторяет временные сетевые ошибки;
    - не падает весь бот, если MAX недоступен.
    """

    def __init__(
        self,
        token: Optional[str] = None,
        *,
        connect_timeout: float = 10.0,
        read_timeout: float = 30.0,
        write_timeout: float = 15.0,
        pool_timeout: float = 10.0,
        retries: int = 3,
    ) -> None:
        self.token = token or MAX_BOT_TOKEN

        if not self.token:
            raise ValueError(
                "MAX bot token is not set (env MAX_BOT_TOKEN)"
            )

        self.base_url = MAX_API_BASE_URL
        self.retries = retries

        # Раздельные таймауты: соединение, ожидание ответа,
        # отправка данных и ожидание свободного соединения.
        timeout = httpx.Timeout(
            connect=connect_timeout,
            read=read_timeout,
            write=write_timeout,
            pool=pool_timeout,
        )

        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={
                "Authorization": self.token,
                "Content-Type": "application/json",
            },
            timeout=timeout,
        )

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
        Выполняет запрос к MAX API с повторами.

        Повторяются только временные ошибки:
        - ConnectTimeout: не удалось установить соединение;
        - ConnectError: сеть, DNS или сервер недоступны;
        - ReadTimeout: соединение установлено, но ответ не пришёл.
        """
        last_exc = None

        # retries = 3 означает до 4 попыток: первая + 3 повтора.
        for attempt in range(self.retries + 1):
            try:
                response = await self.client.request(
                    method,
                    url,
                    params=params,
                    json=json,
                )

                # Ошибки API (400, 401, 403, 404, 422, 500 и т.д.)
                # не имеет смысла повторять: это не сетевой сбой.
                if response.status_code >= 400:
                    try:
                        body = response.json()
                    except Exception:
                        body = response.text

                    logger.error(
                        "MAX API error (%s): status=%s body=%s",
                        context or url,
                        response.status_code,
                        body,
                    )

                    return {}

                return response.json()

            except (
                httpx.ConnectTimeout,
                httpx.ConnectError,
                httpx.ReadTimeout,
            ) as exc:
                last_exc = exc

                logger.warning(
                    "MAX API temporary error (%s): attempt=%s/%s, %s",
                    context or url,
                    attempt + 1,
                    self.retries + 1,
                    type(exc).__name__,
                )

                # Последняя попытка — выходим.
                if attempt >= self.retries:
                    break

                # Пауза между попытками: 1, 2, 3 секунды.
                await asyncio.sleep(attempt + 1)

            except Exception as exc:
                last_exc = exc

                logger.exception(
                    "MAX API unexpected error (%s)",
                    context or url,
                )
                break

        if last_exc:
            logger.error(
                "MAX API request failed (%s): %r",
                context or url,
                last_exc,
            )

        return {}

    async def send_text_to_user(
        self,
        user_id: int,
        text: str,
        attachments: Optional[List[dict]] = None,
    ) -> Dict[str, Any]:
        """Отправляет текстовое сообщение пользователю."""
        params = {"user_id": str(user_id)}
        payload = {"text": text}

        if attachments:
            payload["attachments"] = attachments

        response = await self._request(
            "POST",
            "/messages",
            params=params,
            json=payload,
            context=f"user user_id={user_id}",
        )

        logger.debug(
            "MAX send_text_to_user response: %s",
            response,
        )

        return response

    async def send_text_to_chat(
        self,
        chat_id: int,
        text: str,
        attachments: Optional[List[dict]] = None,
    ) -> Dict[str, Any]:
        """Отправляет текстовое сообщение в чат."""
        params = {"chat_id": str(chat_id)}
        payload = {"text": text}

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
        """Подтверждает нажатие inline-кнопки."""
        params = {"callback_id": callback_id}
        payload = {}

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
        Загружает файл и отправляет его пользователю.

        Логика:
        1. Получаем upload URL.
        2. Загружаем файл.
        3. Ждём, пока MAX подготовит вложение.
        4. Отправляем сообщение с файлом.
        """
        # 1. Получаем ссылку для загрузки файла.
        upload_response = await self._request(
            "POST",
            "/uploads",
            params={"type": "file"},
            context="get_upload_url",
        )

        if not upload_response or "url" not in upload_response:
            raise Exception("Не удалось получить URL для загрузки файла")

        upload_url = upload_response["url"]

        # 2. Загружаем сам файл.
        async with httpx.AsyncClient() as client:
            files = {
                "data": (
                    filename,
                    file_bytes,
                    "application/pdf",
                )
            }

            upload_result = await client.post(
                upload_url,
                files=files,
            )
            upload_result.raise_for_status()
            upload_data = upload_result.json()

        attachment_token = upload_data.get("token")

        if not attachment_token:
            raise Exception(
                "Не удалось получить токен вложения после загрузки"
            )

        # 3. Даём MAX время подготовить файл.
        await asyncio.sleep(initial_delay)

        logger.info(
            "Файл загружен, ожидаю %s сек. перед отправкой",
            initial_delay,
        )

        attachments = [
            {
                "type": "file",
                "payload": {
                    "token": attachment_token,
                },
            }
        ]

        # 4. Отправляем сообщение с вложением.
        for attempt in range(max_retries):
            try:
                if caption:
                    response = await self.send_text_to_user(
                        user_id,
                        caption,
                        attachments,
                    )
                else:
                    response = await self.send_text_to_user(
                        user_id,
                        "",
                        attachments,
                    )

                # MAX иногда ещё не успел обработать файл.
                if (
                    isinstance(response, dict)
                    and response.get("code") == "attachment.not.ready"
                ):
                    delay = base_delay * (2 ** attempt)

                    logger.warning(
                        "Вложение ещё не готово, попытка %s/%s. "
                        "Повтор через %s сек.",
                        attempt + 1,
                        max_retries,
                        delay,
                    )

                    if attempt == max_retries - 1:
                        raise Exception(
                            "attachment.not.ready после всех попыток"
                        )

                    await asyncio.sleep(delay)
                    continue

                return response

            except Exception as exc:
                logger.warning(
                    "Попытка %s/%s отправки файла не удалась: %s",
                    attempt + 1,
                    max_retries,
                    exc,
                )

                if attempt == max_retries - 1:
                    raise

                delay = base_delay * (2 ** attempt)
                await asyncio.sleep(delay)

        return {}

    async def close(self) -> None:
        """Закрывает HTTP-клиент."""
        await self.client.aclose()


class MaxOrderBotClient(MaxClient):
    """Клиент для бота, который отправляет заявки мастерам."""

    def __init__(
        self,
        token: Optional[str] = None,
        **kwargs,
    ) -> None:
        order_token = token or os.getenv("MAX_ORDER_BOT_TOKEN")

        if not order_token:
            raise ValueError("MAX_ORDER_BOT_TOKEN is not set")

        super().__init__(token=order_token, **kwargs)