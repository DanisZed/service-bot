# app/api/master_auth.py
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Response, status, Query, Cookie, Body
from fastapi.responses import RedirectResponse, JSONResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal
from app.db.models import Master

import jwt
from jwt import InvalidTokenError


router = APIRouter(prefix="/api/master/auth", tags=["master-auth"])


SECRET_KEY = os.getenv(
    "SECRET_KEY",
    "4gOWnBzTs7ec0HTS12rpErnILvUGq-ZyK2HFWsdBRK5QVAGQeQnEgp1fmjEmzzbn1v3TAu_i2GLQQ14z7Es3QA",
)
ACCESS_TOKEN_COOKIE_NAME = "access_token"

# База для мобильной/веб панели (app.*)
PANEL_BASE_URL = os.getenv("PANEL_BASE_URL", "https://app.rbt-crm.ru")

# Общие настройки куки для всех поддоменов rbt-crm.ru
COOKIE_DOMAIN = os.getenv("COOKIE_DOMAIN", ".rbt-crm.ru")
COOKIE_SAMESITE = os.getenv("COOKIE_SAMESITE", "lax")  # или "none" при необходимости
COOKIE_MAX_AGE = 60 * 60 * 24 * 7  # 7 дней


class PanelTokenOut(BaseModel):
    login_url: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    master_id: int
    name: Optional[str] = None


class MasterMeOut(BaseModel):
    master_id: int
    name: Optional[str] = None
    plan: Optional[str] = None


class CompleteRegistrationRequest(BaseModel):
    master_id: str


class CompleteRegistrationResponse(BaseModel):
    success: bool
    master_id: str
    name: str
    role: str
    message: Optional[str] = None


class VerifyCodeRequest(BaseModel):
    code: str


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _create_access_token(master: Master) -> str:
    payload = {
        "sub": str(master.id),
        "role": "admin" if getattr(master, "is_admin", False) else "master",
        "exp": _now() + timedelta(days=7),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")


def _encode_cookie(response: Response, token: str):
    response.set_cookie(
        key=ACCESS_TOKEN_COOKIE_NAME,
        value=token,
        httponly=True,
        secure=True,
        samesite=COOKIE_SAMESITE,
        max_age=COOKIE_MAX_AGE,
        path="/",
        domain=COOKIE_DOMAIN,
    )


def _decode_master_id_from_token(token: str) -> int:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
    except InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
    if payload.get("role") not in {"master", "admin"}:
        raise HTTPException(status_code=403, detail="Invalid role")
    try:
        return int(payload.get("sub"))
    except (TypeError, ValueError):
        raise HTTPException(status_code=401, detail="Invalid token payload")


@router.get("/panel-token", response_model=PanelTokenOut)
async def generate_panel_token(
    max_user_id: int = Query(...),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Master).where(Master.max_user_id == max_user_id))
    master = result.scalar_one_or_none()

    if not master:
        master = Master(
            max_user_id=max_user_id,
            is_active=1,
            plan="free",
            created_at=_now(),
        )
        db.add(master)
        await db.commit()
        await db.refresh(master)

    if not master.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Master is inactive",
        )

    payload = {
        "sub": str(master.id),
        "exp": _now() + timedelta(hours=24),
        "type": "max_auto_login",
    }
    token = jwt.encode(payload, SECRET_KEY, algorithm="HS256")

    login_url = f"{PANEL_BASE_URL}/panel?token={token}"
    return PanelTokenOut(login_url=login_url)


@router.get("/panel/consume")
async def consume_panel_token(
    token: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
    except InvalidTokenError:
        raise HTTPException(status_code=400, detail="Invalid token")

    if payload.get("type") != "max_auto_login":
        raise HTTPException(status_code=400, detail="Invalid token type")

    master_id = int(payload.get("sub"))
    result = await db.execute(select(Master).where(Master.id == master_id))
    master = result.scalar_one_or_none()
    if not master or not master.is_active:
        raise HTTPException(status_code=401, detail="Master not found or inactive")

    access_token = _create_access_token(master)
    # Здесь пока оставляем редирект в мобильную панель:
    resp = RedirectResponse(url=f"{PANEL_BASE_URL}/app/dashboard", status_code=302)
    _encode_cookie(resp, access_token)
    return resp


@router.post("/verify-code", response_model=TokenOut)
async def verify_code(
    payload: VerifyCodeRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    code = payload.code.strip()
    if not code:
        raise HTTPException(status_code=400, detail="Empty code")

    result = await db.execute(select(Master).where(Master.login_code == code))
    master = result.scalar_one_or_none()
    if not master:
        raise HTTPException(status_code=400, detail="Invalid code")

    expires_at = master.login_code_expires_at
    if not expires_at:
        raise HTTPException(status_code=400, detail="Code expired")

    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    if expires_at < _now():
        raise HTTPException(status_code=400, detail="Code expired")

    master.login_code = None
    master.login_code_expires_at = None
    await db.commit()

    access_token = _create_access_token(master)
    _encode_cookie(response, access_token)

    return TokenOut(
        access_token=access_token,
        token_type="bearer",
        master_id=master.id,
        name=master.name or "",
    )


@router.get("/me", response_model=MasterMeOut)
async def get_current_master(
    access_token: Optional[str] = Cookie(
        default=None, alias=ACCESS_TOKEN_COOKIE_NAME
    ),
    db: AsyncSession = Depends(get_db),
):
    if not access_token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    master_id = _decode_master_id_from_token(access_token)
    result = await db.execute(select(Master).where(Master.id == master_id))
    master = result.scalar_one_or_none()
    if not master or not master.is_active:
        raise HTTPException(status_code=401, detail="Master not found or inactive")

    return MasterMeOut(
        master_id=master.id,
        name=master.name,
        plan=master.plan,
    )


@router.post("/complete-registration", response_model=CompleteRegistrationResponse)
async def complete_registration(
    request: CompleteRegistrationRequest,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Master).where(Master.master_id == request.master_id)
    )
    master = result.scalar_one_or_none()

    if not master:
        raise HTTPException(status_code=404, detail="Master not found")

    if master.is_active != 1:
        raise HTTPException(status_code=400, detail="Master not activated yet")

    service_name = ""
    if master.service_center:
        service_name = master.service_center.service_name
    display_name = master.name or service_name or ""

    from app.services.token_service import create_access_token

    access_token = create_access_token(
        data={
            "sub": str(master.id),
            "master_id": master.master_id,
            "role": "admin" if master.is_admin else "master",
        }
    )

    response_data = CompleteRegistrationResponse(
        success=True,
        master_id=master.master_id,
        name=display_name,
        role="Администратор" if master.is_admin else "Мастер",
    )

    resp = JSONResponse(content=response_data.model_dump())
    _encode_cookie(resp, access_token)
    return resp


@router.post("/logout", status_code=status.HTTP_200_OK)
async def logout(response: Response):
    response.delete_cookie(ACCESS_TOKEN_COOKIE_NAME, path="/", domain=COOKIE_DOMAIN)
    return {"detail": "Logged out"}