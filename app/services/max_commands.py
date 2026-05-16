# app/services/max_commands.py

from typing import Any, Dict, Optional, Tuple, List

import os
import httpx

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")  # backend
# фронт нам возвращает из эндпоинта, так что PANEL_URL больше не нужен


async def _get_login_url_for_max_user(max_user_id: int) -> str:
    """
    Вызывает backend /api/master/auth/request-code-by-max и
    возвращает login_url вида http://.../login?code=XXXXXX.
    """
    url = f"{API_BASE_URL}/api/master/auth/request-code-by-max"
    async with httpx.AsyncClient(timeout=5.0) as client:
        resp = await client.post(url, params={"max_user_id": max_user_id})
    resp.raise_for_status()
    data = resp.json()
    return data["login_url"]


async def handle_command(
    user_id: int,
    text: str,
) -> Tuple[Optional[str], Optional[List[Dict[str, Any]]]]:
    lower = text.strip().lower()

    if lower == "/panel":
        # получаем одноразовый код и ссылку логина
        link = await _get_login_url_for_max_user(user_id)

        reply_text = (
            "Откройте панель мастера по кнопке ниже.\n\n"
            "Мы авторизуем вас автоматически по вашему аккаунту MAX."
        )

        buttons_rows: List[List[dict]] = [
            [
                {
                    "type": "link",
                    "text": "Открыть панель мастера",
                    "url": link,
                }
            ]
        ]

        attachments: List[Dict[str, Any]] = [
            {
                "type": "inline_keyboard",
                "payload": {"buttons": buttons_rows},
            }
        ]

        return reply_text, attachments

    return None, None