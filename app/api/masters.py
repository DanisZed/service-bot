# app/api/masters.py
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.db.models import Master, ServiceCenter
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
    is_admin: int
    # service_id и service_name теперь не являются прямыми полями мастера,
    # их можно получить через связанный объект, но для совместимости со старым фронтом
    # можно добавить computed поля, либо оставить так:
    service_id: Optional[str] = None
    service_name: Optional[str] = None


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
    # Получаем данные о сервис-центре, если есть
    service_id = None
    service_name = None
    if current_master.service_center:
        service_id = current_master.service_center.service_id
        service_name = current_master.service_center.service_name

    return {
        "id": current_master.id,
        "master_id": current_master.master_id,
        "name": current_master.name,
        "lastname": current_master.lastname,
        "phone": current_master.phone,
        "email": current_master.email,
        "service_id": service_id,
        "service_name": service_name,
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
    if current_master.id != master_id and current_master.is_admin != 1:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Недостаточно прав для редактирования"
        )
    
    result = await db.execute(select(Master).where(Master.id == master_id))
    target_master = result.scalar_one_or_none()
    if not target_master:
        raise HTTPException(status_code=404, detail="Мастер не найден")
    
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
    Очистить service_center_id у мастера (отвязать от сервисного центра)
    Только для администраторов
    """
    if current_master.is_admin != 1:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Только администратор может отвязывать мастеров"
        )
    
    result = await db.execute(select(Master).where(Master.id == master_id))
    target_master = result.scalar_one_or_none()
    if not target_master:
        raise HTTPException(status_code=404, detail="Мастер не найден")
    
    # Проверяем, что мастер принадлежит тому же сервис-центру, что и админ
    if not current_master.service_center or target_master.service_center_id != current_master.service_center.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Мастер не принадлежит вашему сервисному центру"
        )
    
    target_master.service_center_id = None
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
    Получить всех мастеров, привязанных к сервисному центру (по строковому service_id)
    Только для администраторов этого сервиса
    """
    if current_master.is_admin != 1:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Только администратор может просматривать мастеров сервиса"
        )
    
    # Находим сервис-центр по service_id
    sc_result = await db.execute(select(ServiceCenter).where(ServiceCenter.service_id == service_id))
    service_center = sc_result.scalar_one_or_none()
    if not service_center:
        raise HTTPException(status_code=404, detail="Сервисный центр не найден")
    
    # Проверяем, что текущий админ принадлежит этому центру
    if not current_master.service_center or current_master.service_center.id != service_center.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Доступ запрещён"
        )
    
    result = await db.execute(
        select(Master).where(
            Master.service_center_id == service_center.id,
            Master.is_admin == 0
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