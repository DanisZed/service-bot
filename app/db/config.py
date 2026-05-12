import os

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://servicebot_app:D1a9n8i0s@localhost:5432/servicebot",
)