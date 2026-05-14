# app/services/max_commands.py

from typing import Any, Dict, Optional, Tuple, List

PANEL_URL = "http://localhost:5173/login"  # потом вынесешь в .env


async def handle_command(
    user_id: int,
    text: str,
) -> Tuple[Optional[str], Optional[List[Dict[str, Any]]]]:
    """
    Обрабатывает команды (начинающиеся с /) для MAX.
    Если команда распознана — возвращает (reply_text, attachments).
    Если команда не распознана — (None, None), и дальше решает диалоговый сервис.
    """
    lower = text.strip().lower()

    # /panel — ссылка на панель мастера
    if lower == "/panel":
        link = f"{PANEL_URL}?max_user_id={user_id}"

        reply_text = (
            "Откройте панель мастера по кнопке ниже.\n\n"
            "Мы авторизуем вас автоматически по аккаунту MAX."
        )

        buttons_rows: List[list[Dict[str, Any]]] = []
        buttons_rows.append(
            [
                {
                    "type": "link",
                    "text": "Открыть панель мастера",
                    "url": link,
                }
            ]
        )

        attachments: List[Dict[str, Any]] = [
            {
                "type": "buttons",
                "buttons": buttons_rows,
            }
        ]

        return reply_text, attachments

    # сюда позже добавишь новые команды:
    # if lower == "/pay": ...
    # if lower == "/profile": ...

    return None, None