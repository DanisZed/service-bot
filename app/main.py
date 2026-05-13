import os
from pathlib import Path
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware  # ← добавить

# Загружаем .env из корня проекта
BASE_DIR = Path(__file__).resolve().parent.parent  # app/.. = service-bot
load_dotenv(BASE_DIR / ".env")

from app.api.max_webhook import router as max_router
from app.api.master_auth import router as master_auth_router
from app.api.requests import router as requests_router

app = FastAPI()

# CORS
origins = [
    "http://192.168.2.122:5173",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,     # можно временно ["*"] для отладки
    allow_credentials=True,
    allow_methods=["*"],       # важно, чтобы OPTIONS не падал
    allow_headers=["*"],
)

# Роутеры
app.include_router(max_router)
app.include_router(master_auth_router)
app.include_router(requests_router)