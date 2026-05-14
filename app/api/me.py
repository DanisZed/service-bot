from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.deps import get_current_master

router = APIRouter(prefix="/api/me", tags=["me"])


class MeOut(BaseModel):
    username: str
    user_id: int

@router.get("", response_model=MeOut)
async def get_me(current_master=Depends(get_current_master)):
    # предполагаю, что у Master есть поля name и max_user_id
    return MeOut(
        username=current_master.name,
        user_id=current_master.max_user_id,
    )