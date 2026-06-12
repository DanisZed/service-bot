from fastapi import APIRouter, Depends, HTTPException, status, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from datetime import datetime, timezone
import jwt
import os

from app.api.deps import get_db
from app.db.models import Master
from app.db.session import AsyncSessionLocal

router = APIRouter(prefix="/api/auth", tags=["auth"])

SECRET_KEY = os.getenv("SECRET_KEY")
ACCESS_TOKEN_COOKIE_NAME = "access_token"

class LoginByCodeInput(BaseModel):
    code: str

class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"

def make_jwt_for_master(master: Master) -> str:
    payload = {
        "sub": str(master.id),
        "exp": datetime.now(timezone.utc) + timedelta(days=7),
        "role": "master"
    }
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")

@router.post("/verify-code")
async def login_by_code(
    payload: LoginByCodeInput,
    response: Response,
):
    code = payload.code.strip()
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Master).where(Master.login_code == code)
        )
        master = result.scalar_one_or_none()
        if not master:
            raise HTTPException(400, "Неверный код")
        if not master.login_code_expires_at or master.login_code_expires_at < datetime.now(timezone.utc):
            raise HTTPException(400, "Код истёк")
        master.login_code = None
        master.login_code_expires_at = None
        await session.commit()
        token = make_jwt_for_master(master)
        response.set_cookie(
            key=ACCESS_TOKEN_COOKIE_NAME,
            value=token,
            httponly=True,
            secure=False,   # на проде True для https
            samesite="lax",
            max_age=60*60*24*7,
        )
        return {"access_token": token, "token_type": "bearer"}

@router.get("/max_deeplink")
async def login_via_max_deeplink(
    max_user_id: int = Query(...),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Master).where(Master.max_user_id == max_user_id))
    master = result.scalar_one_or_none()
    if not master:
        master = Master(max_user_id=max_user_id, is_active=1, plan="free")
        db.add(master)
        await db.commit()
        await db.refresh(master)
    if not master.is_active:
        raise HTTPException(403, "Master is inactive")
    token = make_jwt_for_master(master)
    return TokenOut(access_token=token)

@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie(ACCESS_TOKEN_COOKIE_NAME)
    return {"detail": "Logged out"}