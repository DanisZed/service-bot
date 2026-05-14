from datetime import datetime
from typing import Any

import jwt
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.core.config import SECRET_KEY  # или откуда ты сейчас берёшь SECRET_KEY
from app.db.models import Master

SECRET_KEY = "4gOWnBzTs7ec0HTS12rpErnILvUGq-ZyK2HFWsdBRK5QVAGQeQnEgp1fmjEmzzbn1v3TAu_i2GLQQ14z7Es3QA"

router = APIRouter(prefix="/api/auth", tags=["auth"])


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


@router.get("/max_deeplink", response_model=TokenOut)
async def login_via_max_deeplink(
    max_user_id: int = Query(..., description="user_id мастера в MAX"),
    db: AsyncSession = Depends(get_db),
) -> Any:
    # ищем мастера по max_user_id
    result = await db.execute(
        select(Master).where(Master.max_user_id == max_user_id)
    )
    master = result.scalar_one_or_none()

    # если не нашли — создаём «пустого» мастера
    if not master:
        master = Master(
            max_user_id=max_user_id,
            is_active=1,
            plan="free",
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
        "iat": int(datetime.utcnow().timestamp()),
    }
    token = jwt.encode(payload, SECRET_KEY, algorithm="HS256")

    return TokenOut(access_token=token)