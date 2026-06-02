# app/api/masters.py
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.db.models import Master
from app.api.deps import get_current_master

router = APIRouter(prefix="/api/masters", tags=["masters"])


# ========== СХЕМЫ ==========

class MasterOut(BaseModel):
    id: int
    master_id: str
    name: Optional[str] = None
    lastname: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    service_id: Optional[str] = None
    service_name: Optional[str] = None
    is_admin: int


class UpdatePhoneRequest(BaseModel):
    phone: str


class ClearServiceResponse(BaseModel):
    success: bool
    message: str


class LinkedMasterOut(BaseModel):
    id: int
    master_id: str
    name: Optional[str] = None
    lastname: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None


# ========== ЭНДПОИНТЫ ==========

@router.get("/me")
async def get_current_master_info(current_master: Master = Depends(get_current_master)):
    """
    Получить информацию о текущем авторизованном мастере
    """
    return {
        "id": current_master.id,
        "master_id": current_master.master_id,
        "name": current_master.name,
        "lastname": current_master.lastname,
        "phone": current_master.phone,
        "email": current_master.email,
        "service_id": current_master.service_id,
        "service_name": current_master.service_name,
        "is_admin": current_master.is_admin,
        "role": "admin" if current_master.is_admin == 1 else "master",
    }


@router.patch("/{master_id}/phone")
async def update_master_phone(
    master_id: int,
    request: UpdatePhoneRequest,
    current_master: Master = Depends(get_current_master),
    db: AsyncSession = Depends(get_session),
):
    """
    Обновить телефон мастера (только для своего профиля или админа)
    """
    # Проверяем права: либо свой профиль, либо админ
    if current_master.id != master_id and current_master.is_admin != 1:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Недостаточно прав для редактирования"
        )
    
    # Находим мастера
    result = await db.execute(select(Master).where(Master.id == master_id))
    target_master = result.scalar_one_or_none()
    
    if not target_master:
        raise HTTPException(status_code=404, detail="Мастер не найден")
    
    # Обновляем телефон
    target_master.phone = request.phone
    await db.commit()
    await db.refresh(target_master)
    
    return {
        "success": True,
        "phone": target_master.phone,
        "master_id": target_master.master_id
    }


@router.patch("/{master_id}/clear-service", response_model=ClearServiceResponse)
async def clear_master_service(
    master_id: int,
    current_master: Master = Depends(get_current_master),
    db: AsyncSession = Depends(get_session),
):
    """
    Очистить service_id и service_name у мастера (отвязать от сервисного центра)
    Только для администраторов
    """
    # Проверяем, что текущий пользователь - админ
    if current_master.is_admin != 1:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Только администратор может отвязывать мастеров"
        )
    
    # Находим целевого мастера
    result = await db.execute(select(Master).where(Master.id == master_id))
    target_master = result.scalar_one_or_none()
    
    if not target_master:
        raise HTTPException(status_code=404, detail="Мастер не найден")
    
    # Проверяем, что мастер принадлежит сервису текущего админа
    if target_master.service_id != current_master.service_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Мастер не принадлежит вашему сервисному центру"
        )
    
    # Очищаем привязку к сервису
    target_master.service_id = None
    target_master.service_name = None
    
    await db.commit()
    
    return ClearServiceResponse(
        success=True,
        message="Мастер отвязан от сервисного центра"
    )


@router.get("/service/{service_id}", response_model=List[LinkedMasterOut])
async def get_masters_by_service(
    service_id: str,
    current_master: Master = Depends(get_current_master),
    db: AsyncSession = Depends(get_session),
):
    """
    Получить всех мастеров, привязанных к сервисному центру
    Только для администраторов этого сервиса
    """
    # Проверяем, что текущий пользователь - админ
    if current_master.is_admin != 1:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Только администратор может просматривать мастеров сервиса"
        )
    
    # Проверяем, что админ имеет доступ к этому сервису
    if current_master.service_id != service_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Доступ запрещён"
        )
    
    # Находим всех мастеров с таким service_id
    result = await db.execute(
        select(Master).where(
            Master.service_id == service_id,
            Master.is_admin == 0  # только обычные мастера, не админы
        )
    )
    masters = result.scalars().all()
    
    return [
        LinkedMasterOut(
            id=m.id,
            master_id=m.master_id,
            name=m.name,
            lastname=m.lastname,
            phone=m.phone,
            email=m.email,
        )
        for m in masters
    ]