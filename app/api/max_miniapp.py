import hashlib
import hmac
import json
import os
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import parse_qsl



from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession



from app.api.deps import get_db
from app.api.master_auth import (
    ACCESS_TOKEN_COOKIE_NAME,
    COOKIE_DOMAIN,
    COOKIE_SAMESITE,
    COOKIE_MAX_AGE,
    _create_access_token,
)
from app.db.models import Master



router = APIRouter(prefix="/api/max", tags=["max-miniapp"])



MAX_ORDER_BOT_TOKEN = os.getenv("MAX_ORDER_BOT_TOKEN")
MAX_INIT_DATA_TTL_SECONDS = 3600




class MaxAuthRequest(BaseModel):
    init_data: str




class MaxMeOut(BaseModel):
    master_id: int
    name: Optional[str] = None
    is_admin: bool
    access_token: str




def _validate_max_init_data(init_data: str) -> dict:
    if not MAX_ORDER_BOT_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="MAX_ORDER_BOT_TOKEN is not configured",
        )



    pairs = dict(parse_qsl(init_data, keep_blank_values=True))
    received_hash = pairs.pop("hash", None)



    if not received_hash:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="initData hash is missing",
        )



    launch_params = "\n".join(
        f"{key}={value}"
        for key, value in sorted(pairs.items())
    )



    secret_key = hmac.new(
        b"WebAppData",
        MAX_ORDER_BOT_TOKEN.encode(),
        hashlib.sha256,
    ).digest()



    calculated_hash = hmac.new(
        secret_key,
        launch_params.encode(),
        hashlib.sha256,
    ).hexdigest()



    if not hmac.compare_digest(calculated_hash, received_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid MAX initData signature",
        )



    auth_date = int(pairs.get("auth_date", "0"))
    now_ts = int(datetime.now(timezone.utc).timestamp())



    if not auth_date or now_ts - auth_date > MAX_INIT_DATA_TTL_SECONDS:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="initData expired",
        )



    user_raw = pairs.get("user")
    if not user_raw:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="MAX user is missing",
        )



    return json.loads(user_raw)




@router.post("/auth", response_model=MaxMeOut)
async def max_auth(
    payload: MaxAuthRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    max_user = _validate_max_init_data(payload.init_data)
    max_user_id = int(max_user["id"])



    result = await db.execute(
        select(Master).where(Master.max_user_id == max_user_id)
    )
    master = result.scalar_one_or_none()



    if not master or not master.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="MAX user is not linked to an active master",
        )



    access_token = _create_access_token(master)



    response.set_cookie(
        key=ACCESS_TOKEN_COOKIE_NAME,
        value=access_token,
        httponly=True,
        secure=True,
        samesite=COOKIE_SAMESITE,
        max_age=COOKIE_MAX_AGE,
        path="/",
        domain=COOKIE_DOMAIN,
    )



    return MaxMeOut(
        master_id=master.id,
        name=master.name,
        is_admin=bool(master.is_admin),
        access_token=access_token,
    )