from __future__ import annotations

from typing import List, Dict

from app.db.models import DeviceCategory, DeviceSubtype


def make_categories_keyboard(categories: List[DeviceCategory]) -> List[Dict]:
    """
    Делает inline-кнопки категорий для MAX.
    payload формата: "cat:<code>"
    """
    buttons = []
    for cat in categories:
        buttons.append(
            {
                "type": "button",
                "text": cat.name,
                "payload": f"cat:{cat.code}",
            }
        )
    if not buttons:
        return []

    return [
        {
            "type": "keyboard",
            "buttons": buttons,
        }
    ]


def make_subtypes_keyboard(subtypes: List[DeviceSubtype]) -> List[Dict]:
    """
    Делает inline-кнопки подтипов техники.
    payload формата: "sub:<code>"
    """
    buttons = []
    for st in subtypes:
        buttons.append(
            {
                "type": "button",
                "text": st.name,
                "payload": f"sub:{st.code}",
            }
        )
    if not buttons:
        return []

    return [
        {
            "type": "keyboard",
            "buttons": buttons,
        }
    ]