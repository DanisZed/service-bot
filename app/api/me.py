# app/api/me.py
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional

from app.api.deps import get_current_master
from app.db.session import get_session
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Master

router = APIRouter(prefix="/api/me", tags=["me"])


class AvatarResponse(BaseModel):
    avatar_url: Optional[str] = None
    full_avatar_url: Optional[str] = None


class MeOut(BaseModel):
    id: int
    master_id: str
    name: Optional[str] = None
    lastname: Optional[str] = None
    avatar_url: Optional[str] = None
    service_name: Optional[str] = None
    role: str
    service_id: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    user_id: int
    display_name: str
    display_role: str
    display_header: Optional[str] = None


class UpdatePhoneRequest(BaseModel):
    phone: str


@router.patch("/phone")
async def update_my_phone(
    data: UpdatePhoneRequest,
    current_master=Depends(get_current_master),
    db: AsyncSession = Depends(get_session),
):
    current_master.phone = data.phone
    await db.commit()
    await db.refresh(current_master)
    return {"success": True, "phone": current_master.phone, "master_id": current_master.master_id}


@router.get("/phone")
async def get_my_phone(current_master=Depends(get_current_master)):
    return {"phone": current_master.phone, "master_id": current_master.master_id}


@router.get("/avatar", response_model=AvatarResponse)
async def get_my_avatar(
    current_master: Master = Depends(get_current_master),
):
    """
    Возвращает URL аватара текущего мастера из базы данных.
    """
    return AvatarResponse(
        avatar_url=current_master.avatar_url,
        full_avatar_url=None
    )


@router.get("", response_model=MeOut)
async def get_me(current_master=Depends(get_current_master)):
    is_admin = current_master.is_admin == 1
    role = "admin" if is_admin else "master"

    name_parts = []
    if current_master.lastname:
        name_parts.append(current_master.lastname)
    if current_master.name:
        name_parts.append(current_master.name)
    display_name = " ".join(name_parts) if name_parts else ("Администратор" if is_admin else "Мастер")

    display_role = "Администратор" if is_admin else "Мастер"
    display_header = None
    if is_admin and current_master.service_center:
        display_header = current_master.service_center.service_name

    service_name = current_master.service_center.service_name if current_master.service_center else None
    service_id = current_master.service_center.service_id if current_master.service_center else None

    return MeOut(
        id=current_master.id,
        master_id=current_master.master_id,
        name=current_master.name,
        lastname=current_master.lastname,
        service_name=service_name,
        role=role,
        service_id=service_id,
        phone=current_master.phone,
        email=current_master.email,
        user_id=current_master.max_user_id,
        display_name=display_name,
        display_role=display_role,
        display_header=display_header,
        avatar_url=current_master.avatar_url,
    )