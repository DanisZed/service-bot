from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import logging

from app.db.session import get_session
from app.db.models import Master, ServiceCenter
from app.api.deps import get_current_master

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/service", tags=["service"])


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


@router.get("/{service_identifier}/masters", response_model=List[LinkedMasterOut])
async def get_service_masters(
    service_identifier: str,
    current_master: Master = Depends(get_current_master),
    db: AsyncSession = Depends(get_session),
):
    """
    Получить всех мастеров, привязанных к сервисному центру
    Только для администраторов этого сервиса
    """
    if current_master.is_admin != 1:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Только администратор может просматривать мастеров сервиса"
        )
    
    # Проверяем, что админ принадлежит сервисному центру с таким service_id
    if not current_master.service_center or current_master.service_center.service_id != service_identifier:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Доступ запрещён"
        )
    
    # Находим всех мастеров с тем же service_center_id
    result = await db.execute(
        select(Master).where(
            Master.service_center_id == current_master.service_center.id,
            Master.is_admin == 0,
            Master.id != current_master.id
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


@router.post("/{service_identifier}/masters", response_model=AddMasterResponse)
async def add_master_to_service(
    service_identifier: str,
    request: AddMasterRequest,
    current_master: Master = Depends(get_current_master),
    db: AsyncSession = Depends(get_session),
):
    """
    Добавить мастера в сервисный центр по его master_id
    Только для администраторов сервиса
    """
    try:
        logger.info(f"Попытка добавления мастера: {request.master_id} в сервис {service_identifier}")
        
        if current_master.is_admin != 1:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Только администратор может добавлять мастеров"
            )
        
        # Находим сервисный центр по service_identifier (строковый service_id)
        result = await db.execute(
            select(ServiceCenter).where(ServiceCenter.service_id == service_identifier)
        )
        service_center = result.scalar_one_or_none()
        if not service_center:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Сервисный центр не найден"
            )
        
        # Проверяем, что текущий админ принадлежит этому центру
        if current_master.service_center_id != service_center.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Доступ запрещён"
            )
        
        # Находим целевого мастера по master_id
        result = await db.execute(
            select(Master).where(Master.master_id == request.master_id)
        )
        target_master = result.scalar_one_or_none()
        
        if not target_master:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Мастер с ID {request.master_id} не найден"
            )
        
        if target_master.is_admin == 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Нельзя добавить администратора в качестве мастера"
            )
        
        if target_master.service_center_id and target_master.service_center_id != service_center.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Мастер уже привязан к другому сервисному центру"
            )
        
        # Привязываем мастера к сервисному центру
        target_master.service_center_id = service_center.id
        
        await db.commit()
        await db.refresh(target_master)
        
        logger.info(f"Мастер {target_master.id} успешно добавлен в сервис {service_identifier}")
        
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
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка при добавлении мастера: {e}")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Внутренняя ошибка сервера: {str(e)}"
        )


@router.patch("/masters/{master_id}/clear-service", response_model=ClearServiceResponse)
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
    
    # Проверяем, что мастер принадлежит тому же сервисному центру, что и админ
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