from fastapi import APIRouter, Depends, HTTPException, status, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import APIRouter, Response, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel  # ← добавляем

from app.api.deps import get_db
from app.db.models import Master

router = APIRouter(prefix="/api/auth", tags=["auth"])


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"

@router.post("/auth/verify-code")
async def login_by_code(payload: LoginByCodeInput):
    code = payload.code.strip()

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Master).where(Master.login_code == code)
        )
        master: Master | None = result.scalar_one_or_none()

        if master is None:
            raise HTTPException(status_code=400, detail="Неверный код")

        if not master.login_code_expires_at:
            raise HTTPException(status_code=400, detail="Код не активен")

        now = datetime.now(timezone.utc)
        if master.login_code_expires_at < now:
            raise HTTPException(status_code=400, detail="Код истёк")

        # всё ок → очищаем код
        master.login_code = None
        master.login_code_expires_at = None
        await session.commit()

        # здесь создаёшь JWT/сессию для мастера
        token = make_jwt_for_master(master)  # твоя функция

    return {"ok": True, "access_token": token, "token_type": "bearer"}   


@router.get("/max_deeplink", response_model=TokenOut)
async def login_via_max_deeplink(
    max_user_id: int = Query(..., description="user_id мастера в MAX"),
    db: AsyncSession = Depends(get_db),
):
    # ищем мастера
    result = await db.execute(
        select(Master).where(Master.max_user_id == max_user_id)
    )
    master = result.scalar_one_or_none()

    if not master:
        # можно либо создать автоматически, либо вернуть 404
        # пока создадим «по‑простому»
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

    # формируем JWT как в login_code
    payload = {
        "sub": str(master.id),
        "iat": int(datetime.utcnow().timestamp()),
        # опционально exp
    }
    token = jwt.encode(payload, SECRET_KEY, algorithm="HS256")

    return TokenOut(access_token=token)

router = APIRouter(prefix="/api/auth", tags=["auth"])

@router.post("/logout", status_code=status.HTTP_200_OK)
async def logout(response: Response):
    # имя куки должно совпадать с тем, как ты её выставляешь при логине
    response.delete_cookie("access_token")
    return {"detail": "Logged out"}