from __future__ import annotations

from typing import Any, Dict, Tuple


class DialogStateStore:
    """
    Простое in-memory хранилище состояния диалога для MAX.
    Ключ: (user_id, chat_id), значение: dict со всеми полями заявки.
    """

    def __init__(self) -> None:
        self._data: Dict[Tuple[int, int], Dict[str, Any]] = {}

    def get(self, user_id: int, chat_id: int) -> Dict[str, Any]:
        return self._data.get((user_id, chat_id), {})

    def set(self, user_id: int, chat_id: int, state: Dict[str, Any]) -> None:
        self._data[(user_id, chat_id)] = state

    def update(self, user_id: int, chat_id: int, **kwargs: Any) -> Dict[str, Any]:
        state = self.get(user_id, chat_id)
        state.update(kwargs)
        self.set(user_id, chat_id, state)
        return state

    def clear(self, user_id: int, chat_id: int) -> None:
        self._data.pop((user_id, chat_id), None)


dialog_state_store = DialogStateStore()