import os
from pydantic import BaseModel


class Settings(BaseModel):
    max_bot_token: str = os.getenv("MAX_BOT_TOKEN", "")
    max_orders_channel_id: str = os.getenv("MAX_ORDERS_CHANNEL_ID", "")
    db_url: str = os.getenv(
        "DATABASE_URL",
        "postgresql://servicebot:password@localhost/servicebot_db",
    )

    work_start_hour: int = 9
    work_end_hour: int = 19
    slot_days_ahead: int = 7


settings = Settings()
