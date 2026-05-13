from fastapi import FastAPI

from app.api.max_webhook import router as max_router
from app.api.master_auth import router as master_auth_router
from app.api.requests import router as requests_router
from app.api import master_panel

app = FastAPI()

app.include_router(max_router)
app.include_router(master_auth_router)
app.include_router(requests_router)
app.include_router(master_panel.router)