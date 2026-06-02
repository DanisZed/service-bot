# app/api/manage_master.py
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.db.models import Master
from app.api.deps import get_current_master

router = APIRouter(prefix="/api/manage-master", tags=["manage_master"])


# ========== СХЕМЫ ==========

class LinkedMasterOut(BaseModel):
    id: int
    master_id: str
    name: Optional[str] = None
    lastname: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None


class AddMasterRequest(BaseModel):
    master_id: str
    service_id: str
    service_name: Optional[str] = None


class AddMasterResponse(BaseModel):
    success: bool
    message: str
    master: Optional[dict] = None


class ClearServiceResponse(BaseModel):
    success: bool
    message: str


# ========== ЭНДПОИНТЫ ==========

@router.get("/service/{service_id}/masters", response_model=List[LinkedMasterOut])
async def get_service_masters(
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
    
    # Находим всех мастеров с таким service_id (не админов)
    result = await db.execute(
        select(Master).where(
            Master.service_id == service_id,
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


@router.post("/service/{service_id}/masters", response_model=AddMasterResponse)
async def add_master_to_service(
    service_id: str,
    request: AddMasterRequest,
    current_master: Master = Depends(get_current_master),
    db: AsyncSession = Depends(get_session),
):
    """
    Добавить мастера в сервисный центр по его master_id
    Только для администраторов сервиса
    """
    # Проверяем, что текущий пользователь - админ
    if current_master.is_admin != 1:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Только администратор может добавлять мастеров"
        )
    
    # Проверяем, что админ имеет доступ к этому сервису
    if current_master.service_id != service_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Доступ запрещён"
        )
    
    # Находим мастера по master_id
    result = await db.execute(
        select(Master).where(Master.master_id == request.master_id)
    )
    target_master = result.scalar_one_or_none()
    
    if not target_master:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Мастер с ID {request.master_id} не найден"
        )
    
    # Проверяем, что мастер не админ
    if target_master.is_admin == 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Нельзя добавить администратора в качестве мастера"
        )
    
    # Проверяем, что мастер не привязан к другому сервису
    if target_master.service_id and target_master.service_id != service_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Мастер уже привязан к сервису {target_master.service_name}"
        )
    
    # Привязываем мастера к сервису
    target_master.service_id = request.service_id
    target_master.service_name = request.service_name
    
    await db.commit()
    await db.refresh(target_master)
    
    return AddMasterResponse(
        success=True,
        message="Мастер успешно добавлен в сервисный центр",
        master={
            "id": target_master.id,
            "master_id": target_master.master_id,
            "name": target_master.name,
            "lastname": target_master.lastname,
            "phone": target_master.phone,
            "email": target_master.email,
        }
    )


@router.patch("/masters/{master_id}/clear-service", response_model=ClearServiceResponse)
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