# app/api/deps.py
import os
import jwt
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.db.models import Master

SECRET_KEY = os.getenv(
    "SECRET_KEY",
    "4gOWnBzTs7ec0HTS12rpErnILvUGq-ZyK2HFWsdBRK5QVAGQeQnEgp1fmjEmzzbn1v3TAu_i2GLQQ14z7Es3QA",
)
ALGORITHM = "HS256"
ACCESS_TOKEN_COOKIE_NAME = "access_token"


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session


async def get_current_master(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    token = request.cookies.get(ACCESS_TOKEN_COOKIE_NAME)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )

    master_id = payload.get("sub")
    if master_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )

    result = await db.execute(
        select(Master).where(Master.id == int(master_id))
    )
    master = result.scalars().first()
    if not master:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Master not found",
        )

    return master