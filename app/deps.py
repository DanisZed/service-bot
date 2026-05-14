import os

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal
from app.db.models import Master

SECRET_KEY = os.getenv("SECRET_KEY", "CHANGE_ME")
security = HTTPBearer()


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session


async def get_current_master(
    creds: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> Master:
    token = creds.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )

    master_id = int(payload.get("sub") or 0)
    result = await db.execute(
        select(Master).where(Master.id == master_id)
    )
    master = result.scalars().first()
    if not master:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Master not found",
        )

    return master