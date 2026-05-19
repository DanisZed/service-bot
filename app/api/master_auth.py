import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional  # <-- добавили

import jwt
from fastapi import APIRouter, Depends, HTTPException, Response, status, Query
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
)  # заменишь на свой

ACCESS_TOKEN_COOKIE_NAME = "access_token"


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


@router.post("/request-code-by-max", response_model=RequestCodeByMaxOut)
async def request_login_code_by_max(
    max_user_id: int = Query(..., description="user_id мастера в MAX"),
    db: AsyncSession = Depends(get_db),
):
    """
    Генерирует login_code для мастера по max_user_id и возвращает ссылку
    для входа в панель. Ничего никуда не отправляет — код используется
    первым ботом в кнопке.
    """
    result = await db.execute(
        select(Master).where(Master.max_user_id == max_user_id)
    )
    master = result.scalars().first()

    # если не нашли — создаём мастера на лету
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

    code = f"{secrets.randbelow(999999):06d}"  # 6-значный код
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)

    master.login_code = code
    master.login_code_expires_at = expires_at
    await db.commit()

    # актуальный URL панели из env, по умолчанию — твой новый домен
    frontend_base = os.getenv("FRONTEND_BASE_URL", "https://panel.master-rbt-crm.ru")
    login_url = f"{frontend_base}/login?code={code}"

    return RequestCodeByMaxOut(code=code, login_url=login_url)


@router.post("/verify-code", response_model=TokenOut)
async def verify_login_code(
    payload: VerifyCodeRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """
    Проверяет код из MAX, обнуляет его и выдаёт JWT для мастера.
    Параллельно ставит JWT в HttpOnly-куку access_token.
    """
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

    # одноразовый код: очищаем
    master.login_code = None
    master.login_code_expires_at = None
    await db.commit()

    payload_jwt = {
        "sub": str(master.id),
        "role": "master",
        "exp": datetime.now(timezone.utc) + timedelta(days=7),
    }
    access_token = jwt.encode(payload_jwt, SECRET_KEY, algorithm="HS256")

    # ставим токен в куку
    response.set_cookie(
        key=ACCESS_TOKEN_COOKIE_NAME,
        value=access_token,
        httponly=True,
        secure=False,  # включишь True на https
        samesite="lax",
        max_age=60 * 60 * 24 * 7,  # 7 дней
    )

    return TokenOut(
        access_token=access_token,
        token_type="bearer",
        master_id=master.id,
        name=master.name or "",
    )


@router.post("/logout", status_code=status.HTTP_200_OK)
async def logout(response: Response):
    """
    Logout мастера: удаляем куку с токеном.
    """
    response.delete_cookie(ACCESS_TOKEN_COOKIE_NAME)
    return {"detail": "Logged out"}