# config.py
import os
from dotenv import load_dotenv

# Загружаем переменные из .env
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

# Опционально: проверка, что переменная загрузилась
if not DATABASE_URL:
    raise ValueError("DATABASE_URL не задан в .env файле")