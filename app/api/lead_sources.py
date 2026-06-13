from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.db.models import LeadSource, Master
from app.api.deps import get_current_master

router = APIRouter(prefix="/api/lead-sources", tags=["lead_sources"])


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


@router.get("", response_model=List[LeadSourceOut])
async def get_sources(
    db: AsyncSession = Depends(get_session),
    current_master=Depends(get_current_master),
):
    """Получить все источники, доступные текущему мастеру или администратору"""
    if current_master.is_admin == 1:
        # Администратор: видит источники всех мастеров своего сервис-центра
        if not current_master.service_center:
            return []
        # Находим всех мастеров этого сервис-центра
        masters_result = await db.execute(
            select(Master.id).where(Master.service_center_id == current_master.service_center.id)
        )
        master_ids = [row[0] for row in masters_result.all()]
        if not master_ids:
            return []
        stmt = select(LeadSource).where(LeadSource.master_id.in_(master_ids)).order_by(LeadSource.name)
    else:
        # Обычный мастер: только свои источники
        stmt = select(LeadSource).where(LeadSource.master_id == current_master.id).order_by(LeadSource.name)
    
    result = await db.execute(stmt)
    sources = result.scalars().all()
    
    return [
        LeadSourceOut(
            id=s.id,
            name=s.name,
            code=s.code,
            description=s.description,
            is_active=s.is_active,
            is_advertisable=s.is_advertisable,
        )
        for s in sources
    ]


@router.post("", response_model=LeadSourceOut, status_code=status.HTTP_201_CREATED)
async def create_source(
    payload: LeadSourceCreate,
    db: AsyncSession = Depends(get_session),
    current_master=Depends(get_current_master),
):
    """Создать новый источник (привязывается к текущему мастеру)"""
    # Проверяем, что источник с таким именем уже не существует у этого мастера
    existing = await db.execute(
        select(LeadSource).where(
            LeadSource.master_id == current_master.id,
            LeadSource.name == payload.name
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(400, "Источник с таким именем уже существует")
    
    source = LeadSource(
        name=payload.name,
        code=payload.code,
        description=payload.description,
        is_active=True,
        is_advertisable=payload.is_advertisable,
        master_id=current_master.id,
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
        is_advertisable=source.is_advertisable,
    )


@router.patch("/{source_id}", response_model=LeadSourceOut)
async def update_source(
    source_id: int,
    payload: LeadSourceUpdate,
    db: AsyncSession = Depends(get_session),
    current_master=Depends(get_current_master),
):
    result = await db.execute(select(LeadSource).where(LeadSource.id == source_id))
    source = result.scalar_one_or_none()
    if not source:
        raise HTTPException(404, "Источник не найден")
    
    # Проверка прав: только владелец или админ сервис-центра (но админ видит источники всех мастеров своего центра)
    if current_master.is_admin == 1:
        if not current_master.service_center:
            raise HTTPException(403, "У администратора нет сервис-центра")
        # Находим мастера-владельца источника
        owner_master = await db.get(Master, source.master_id)
        if not owner_master or owner_master.service_center_id != current_master.service_center.id:
            raise HTTPException(403, "Нет прав на редактирование этого источника")
    else:
        if source.master_id != current_master.id:
            raise HTTPException(403, "Нет прав на редактирование")
    
    if payload.name is not None:
        # Проверяем уникальность имени для этого мастера
        existing = await db.execute(
            select(LeadSource).where(
                LeadSource.master_id == source.master_id,
                LeadSource.name == payload.name,
                LeadSource.id != source_id
            )
        )
        if existing.scalar_one_or_none():
            raise HTTPException(400, "Источник с таким именем уже существует")
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
        is_advertisable=source.is_advertisable,
    )


@router.delete("/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_source(
    source_id: int,
    db: AsyncSession = Depends(get_session),
    current_master=Depends(get_current_master),
):
    result = await db.execute(select(LeadSource).where(LeadSource.id == source_id))
    source = result.scalar_one_or_none()
    if not source:
        raise HTTPException(404, "Источник не найден")
    
    # Проверка прав (аналогично update)
    if current_master.is_admin == 1:
        if not current_master.service_center:
            raise HTTPException(403, "У администратора нет сервис-центра")
        owner_master = await db.get(Master, source.master_id)
        if not owner_master or owner_master.service_center_id != current_master.service_center.id:
            raise HTTPException(403, "Нет прав на удаление")
    else:
        if source.master_id != current_master.id:
            raise HTTPException(403, "Нет прав на удаление")
    
    await db.delete(source)
    await db.commit()
    return