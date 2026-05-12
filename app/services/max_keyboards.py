from __future__ import annotations

from typing import List, Dict

from app.db.models import DeviceCategory, DeviceSubtype


def make_categories_keyboard(categories: List[DeviceCategory]) -> List[Dict]:
    """
    Строим inline_keyboard как в документации MAX.

    attachments = [
      {
        "type": "inline_keyboard",
        "payload": {
          "buttons": [
            [ { "type": "callback", "text": "...", "payload": "cat:..." } ],
            ...
          ]
        }
      }
    ]
    """
    if not categories:
        return []

    buttons_rows = []

    for cat in categories:
        buttons_rows.append(
            [
                {
                    "type": "callback",
                    "text": cat.name,
                    "payload": f"cat:{cat.code}",
                }
            ]
        )

    return [
        {
            "type": "inline_keyboard",
            "payload": {
                "buttons": buttons_rows,
            },
        }
    ]


def make_subtypes_keyboard(subtypes: List[DeviceSubtype]) -> List[Dict]:
    """
    Аналогично для подтипов техники.
    payload формата: "sub:<code>"
    """
    if not subtypes:
        return []

    buttons_rows = []

    for st in subtypes:
        buttons_rows.append(
            [
                {
                    "type": "callback",
                    "text": st.name,
                    "payload": f"sub:{st.code}",
                }
            ]
        )

    return [
        {
            "type": "inline_keyboard",
            "payload": {
                "buttons": buttons_rows,
            },
        }
    ]