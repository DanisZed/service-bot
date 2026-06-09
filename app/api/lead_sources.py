from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.db.models import LeadSource
from app.api.deps import get_current_master

router = APIRouter(prefix="/api/lead-sources", tags=["lead_sources"])


# ========== СХЕМЫ ==========

class LeadSourceOut(BaseModel):
    id: int
    name: str
    code: Optional[str] = None
    description: Optional[str] = None
    is_active: bool
    is_advertisable: bool


class LeadSourceCreate(BaseModel):
    name: str
    code: Optional[str] = None
    description: Optional[str] = None
    is_advertisable: bool = False


class LeadSourceUpdate(BaseModel):
    name: Optional[str] = None
    code: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None
    is_advertisable: Optional[bool] = None


# ========== ЭНДПОИНТЫ ==========

@router.get("", response_model=List[LeadSourceOut])
async def get_sources(
    db: AsyncSession = Depends(get_session),
    current_master=Depends(get_current_master),
):
    """Получить все источники заявок (общие + личные)"""
    # Для админа – источники, привязанные к его сервис-центру (по service_id)
    if current_master.is_admin == 1:
        if current_master.service_center:
            stmt = select(LeadSource).where(
                LeadSource.service_id == current_master.service_center.service_id
            ).order_by(LeadSource.name)
        else:
            # У админа нет привязанного сервис-центра – пустой список
            return []
    else:
        # Для обычного мастера – его личные источники
        stmt = select(LeadSource).where(
            LeadSource.master_id == current_master.id
        ).order_by(LeadSource.name)
    
    result = await db.execute(stmt)
    sources = result.scalars().all()
    
    return [
        LeadSourceOut(
            id=s.id,
            name=s.name,
            code=s.code,
            description=s.description,
            is_active=s.is_active,
            is_advertisable=s.is_advertisable
        ) for s in sources
    ]


@router.post("", response_model=LeadSourceOut)
async def create_source(
    payload: LeadSourceCreate,
    db: AsyncSession = Depends(get_session),
    current_master=Depends(get_current_master),
):
    """Создать новый источник заявок"""
    # Определяем service_id и master_id в зависимости от роли
    if current_master.is_admin == 1:
        if not current_master.service_center:
            raise HTTPException(status_code=400, detail="У администратора нет привязанного сервис-центра")
        service_id = current_master.service_center.service_id
        master_id = None
    else:
        service_id = None
        master_id = current_master.id
    
    source = LeadSource(
        name=payload.name,
        code=payload.code,
        description=payload.description,
        is_active=True,
        is_advertisable=payload.is_advertisable,
        service_id=service_id,
        master_id=master_id,
    )
    db.add(source)
    await db.commit()
    await db.refresh(source)
    
    return LeadSourceOut(
        id=source.id,
        name=source.name,
        code=source.code,
        description=source.description,
        is_active=source.is_active,
        is_advertisable=source.is_advertisable
    )


@router.patch("/{source_id}", response_model=LeadSourceOut)
async def update_source(
    source_id: int,
    payload: LeadSourceUpdate,
    db: AsyncSession = Depends(get_session),
    current_master=Depends(get_current_master),
):
    """Обновить источник заявок"""
    result = await db.execute(select(LeadSource).where(LeadSource.id == source_id))
    source = result.scalar_one_or_none()
    
    if not source:
        raise HTTPException(status_code=404, detail="Источник не найден")
    
    # Проверка прав: админ может редактировать источники своего сервиса, мастер – только свои
    if current_master.is_admin == 1:
        if not current_master.service_center or source.service_id != current_master.service_center.service_id:
            raise HTTPException(status_code=403, detail="Нет прав на редактирование этого источника")
    else:
        if source.master_id != current_master.id:
            raise HTTPException(status_code=403, detail="Нет прав на редактирование этого источника")
    
    if payload.name is not None:
        source.name = payload.name
    if payload.code is not None:
        source.code = payload.code
    if payload.description is not None:
        source.description = payload.description
    if payload.is_active is not None:
        source.is_active = payload.is_active
    if payload.is_advertisable is not None:
        source.is_advertisable = payload.is_advertisable
    
    await db.commit()
    await db.refresh(source)
    
    return LeadSourceOut(
        id=source.id,
        name=source.name,
        code=source.code,
        description=source.description,
        is_active=source.is_active,
        is_advertisable=source.is_advertisable
    )


@router.delete("/{source_id}")
async def delete_source(
    source_id: int,
    db: AsyncSession = Depends(get_session),
    current_master=Depends(get_current_master),
):
    """Удалить источник заявок"""
    result = await db.execute(select(LeadSource).where(LeadSource.id == source_id))
    source = result.scalar_one_or_none()
    
    if not source:
        raise HTTPException(status_code=404, detail="Источник не найден")
    
    # Проверка прав (аналогично update)
    if current_master.is_admin == 1:
        if not current_master.service_center or source.service_id != current_master.service_center.service_id:
            raise HTTPException(status_code=403, detail="Нет прав на удаление этого источника")
    else:
        if source.master_id != current_master.id:
            raise HTTPException(status_code=403, detail="Нет прав на удаление этого источника")
    
    await db.delete(source)
    await db.commit()
    
    return {"success": True}