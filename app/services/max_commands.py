# app/services/max_commands.py

from typing import Any, Dict, Optional, Tuple, List

PANEL_URL = "https://daniszed.keenetic.pro//login"  # потом вынесешь в .env


async def handle_command(
    user_id: int,
    text: str,
) -> Tuple[Optional[str], Optional[List[Dict[str, Any]]]]:
    lower = text.strip().lower()

    if lower == "/panel":
        link = f"{PANEL_URL}?max_user_id={user_id}"

        reply_text = (
            "Откройте панель мастера по кнопке ниже.\n\n"
            "Мы авторизуем вас автоматически по аккаунту MAX."
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