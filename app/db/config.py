import os

# DATABASE_URL вида:
# postgresql+asyncpg://user:password@localhost:5432/servicebot
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://Danis@localhost:5432/servicebot",
)