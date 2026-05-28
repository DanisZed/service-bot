# app/api/me.py
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional

from app.api.deps import get_current_master
from app.db.session import get_session
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/api/me", tags=["me"])


class MeOut(BaseModel):
    # Основная информация
    id: int
    master_id: str
    
    # Имя и фамилия
    name: Optional[str] = None
    lastname: Optional[str] = None
    
    # Для сервисного центра
    service_name: Optional[str] = None
    
    # Роль
    role: str  # "admin" или "master"
    
    # ID сервиса
    service_id: Optional[str] = None
    
    # Контактные данные
    phone: Optional[str] = None
    email: Optional[str] = None
    
    # ID в MAX
    user_id: int
    
    # Отображаемые поля
    display_name: str      # "Имя Фамилия"
    display_role: str      # "Администратор" или "Мастер"
    display_header: Optional[str] = None  # название сервиса (только для админа)


# ========== НОВЫЕ ЭНДПОИНТЫ ДЛЯ ТЕЛЕФОНА ==========

class UpdatePhoneRequest(BaseModel):
    phone: str


@router.patch("/phone")
async def update_my_phone(
    data: UpdatePhoneRequest,
    current_master=Depends(get_current_master),
    db: AsyncSession = Depends(get_session),
):
    """
    Обновить телефон текущего авторизованного пользователя (мастера или администратора)
    """
    current_master.phone = data.phone
    await db.commit()
    await db.refresh(current_master)
    
    return {
        "success": True, 
        "phone": current_master.phone,
        "master_id": current_master.master_id
    }


@router.get("/phone")
async def get_my_phone(
    current_master=Depends(get_current_master),
):
    """
    Получить телефон текущего авторизованного пользователя
    """
    return {
        "phone": current_master.phone,
        "master_id": current_master.master_id
    }


# ========== ОСНОВНОЙ ЭНДПОИНТ ==========

@router.get("", response_model=MeOut)
async def get_me(current_master=Depends(get_current_master)):
    """
    Возвращает информацию о текущем мастере/администраторе
    """
    
    # Определяем роль
    is_admin = current_master.is_admin == 1
    role = "admin" if is_admin else "master"
    
    # Формируем display_name (только Имя Фамилия, БЕЗ service_name)
    name_parts = []
    if current_master.lastname:
        name_parts.append(current_master.lastname)
    if current_master.name:
        name_parts.append(current_master.name)
    display_name = " ".join(name_parts) if name_parts else ("Администратор" if is_admin else "Мастер")
    
    # display_role: "Администратор" или "Мастер"
    display_role = "Администратор" if is_admin else "Мастер"
    
    # display_header: название сервиса (только для админа)
    display_header = None
    if is_admin and current_master.service_name:
        display_header = current_master.service_name
    
    return MeOut(
        id=current_master.id,
        master_id=current_master.master_id,
        name=current_master.name,
        lastname=current_master.lastname,
        service_name=current_master.service_name,
        role=role,
        service_id=getattr(current_master, 'service_id', None),
        phone=current_master.phone,
        email=current_master.email,
        user_id=current_master.max_user_id,
        display_name=display_name,
        display_role=display_role,
        display_header=display_header,
    )