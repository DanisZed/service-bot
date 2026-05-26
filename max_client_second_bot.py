# max_client_second_bot.py
import os

from max_client import MaxClient


class MaxClientSecondBot(MaxClient):
    """
    Клиент для второго бота (личный бот мастера).
    Отличается только токеном.
    """

    def __init__(
        self,
        token: str | None = None,
        **kwargs,
    ) -> None:
        # токен второго бота берём из env, если явно не передан
        second_token = token or os.getenv("MAX_SECOND_BOT_TOKEN")
        if not second_token:
            raise ValueError("MAX_SECOND_BOT_TOKEN is not set (env MAX_SECOND_BOT_TOKEN)")

        super().__init__(token=second_token, **kwargs)