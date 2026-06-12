# master_auth.py
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from jwt import InvalidTokenError
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Response,
    status,
    Query,
    Cookie,
)
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal
from app.db.models import Master
from max_client import MaxClient

import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/master/auth", tags=["master-auth"])

MAX_SECOND_BOT_TOKEN = os.getenv("MAX_SECOND_BOT_TOKEN")
SECRET_KEY = os.getenv(
    "SECRET_KEY",
    "4gOWnBzTs7ec0HTS12rpErnILvUGq-ZyK2HFWsdBRK5QVAGQeQnEgp1fmjEmzzbn1v3TAu_i2GLQQ14z7Es3QA",
)
ACCESS_TOKEN_COOKIE_NAME = "access_token"


class CompleteRegistrationRequest(BaseModel):
    master_id: str


class CompleteRegistrationResponse(BaseModel):
    success: bool
    master_id: str
    name: str
    role: str
    message: Optional[str] = None


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session


class VerifyCodeRequest(BaseModel):
    code: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    master_id: int
    name: Optional[str] = None


class RequestCodeByMaxOut(BaseModel):
    code: str
    login_url: str


class MasterMeOut(BaseModel):
    master_id: int
    name: Optional[str] = None
    plan: Optional[str] = None


def _decode_master_id_from_token(token: str) -> int:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
    except InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

    if payload.get("role") != "master":
        raise HTTPException(status_code=403, detail="Invalid role")

    sub = payload.get("sub")
    try:
        return int(sub)
    except (TypeError, ValueError):
        raise HTTPException(status_code=401, detail="Invalid token payload")


@router.post("/request-code-by-max", response_model=RequestCodeByMaxOut)
async def request_login_code_by_max(
    max_user_id: int = Query(..., description="user_id мастера в MAX"),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Master).where(Master.max_user_id == max_user_id)
    )
    master = result.scalars().first()

    if not master:
        master = Master(
            max_user_id=max_user_id,
            is_active=1,
            plan="free",
            created_at=datetime.now(timezone.utc),
        )
        db.add(master)
        await db.commit()
        await db.refresh(master)

    if not master.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Master is inactive",
        )

    code = f"{secrets.randbelow(999999):06d}"
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)

    master.login_code = code
    master.login_code_expires_at = expires_at
    await db.commit()

    frontend_base = os.getenv("FRONTEND_BASE_URL", "https://panel.master-rbt-crm.ru")
    login_url = f"{frontend_base}/login?code={code}"

    return RequestCodeByMaxOut(code=code, login_url=login_url)


@router.post("/verify-code", response_model=TokenOut)
async def verify_login_code(
    payload: VerifyCodeRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    code = payload.code.strip()
    if not code:
        raise HTTPException(status_code=400, detail="Empty code")

    result = await db.execute(select(Master).where(Master.login_code == code))
    master = result.scalars().first()
    if not master:
        raise HTTPException(status_code=400, detail="Invalid code")

    expires_at = master.login_code_expires_at
    if not isinstance(expires_at, datetime):
        raise HTTPException(status_code=400, detail="Code expired")

    now = datetime.now(timezone.utc)

    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    if expires_at < now:
        raise HTTPException(status_code=400, detail="Code expired")

    master.login_code = None
    master.login_code_expires_at = None
    await db.commit()

    payload_jwt = {
        "sub": str(master.id),
        "role": "master",
        "exp": datetime.now(timezone.utc) + timedelta(days=7),
    }
    access_token = jwt.encode(payload_jwt, SECRET_KEY, algorithm="HS256")

    response.set_cookie(
        key=ACCESS_TOKEN_COOKIE_NAME,
        value=access_token,
        httponly=True,
        secure=False,
        samesite="lax",
        max_age=60 * 60 * 24 * 7,
    )

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
    master = result.scalars().first()
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

    # Получаем имя сервисного центра (если есть)
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

    response = CompleteRegistrationResponse(
        success=True,
        master_id=master.master_id,
        name=display_name,
        role="Администратор" if master.is_admin else "Мастер",
    )

    from fastapi.responses import JSONResponse

    resp = JSONResponse(content=response.dict())
    resp.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        max_age=3600 * 24 * 7,
        samesite="lax",
        secure=True,
    )

    return resp


@router.post("/logout", status_code=status.HTTP_200_OK)
async def logout(response: Response):
    response.delete_cookie(ACCESS_TOKEN_COOKIE_NAME)
    return {"detail": "Logged out"}