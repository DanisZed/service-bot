import os
from dotenv import load_dotenv
from fastapi import FastAPI

from app.api.max_webhook import router as max_router
from app.api.master_auth import router as master_auth_router
from app.api.requests import router as requests_router

app = FastAPI()

app.include_router(max_router)
app.include_router(master_auth_router)
app.include_router(requests_router)