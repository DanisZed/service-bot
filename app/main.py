# app/main.py
import os
import logging
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.me import router as me_router
from app.api.requests import router as requests_router
from app.api.master_auth import router as master_auth_router
from app.api.max_webhook import router as max_webhook_router
from app.api.order_webhook import router as order_webhook_router

# Загружаем .env
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

logger = logging.getLogger(__name__)
logger.info(
    "MAIN DEBUG SECRET_KEY=%s MAX_BOT_TOKEN=%s",
    os.getenv("SECRET_KEY"),
    os.getenv("MAX_BOT_TOKEN"),
)

origins = [
    "https://panel.daniszed.keenetic.pro",
    "http://panel.daniszed.keenetic.pro",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://192.168.2.122:5173",
]

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Подключаем ТОЛЬКО нужные роутеры
app.include_router(me_router)
app.include_router(requests_router)
app.include_router(master_auth_router)
app.include_router(max_webhook_router)
app.include_router(order_webhook_router)