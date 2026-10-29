from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import List, Optional

from sqlalchemy import select, or_
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



def get_owner_filters(current_master: Master):
    """
    Возвращает условие доступа к источникам:
    - источники сервис-центра пользователя;
    - личные источники пользователя.
    """
    filters = [
        LeadSource.master_id == current_master.id,
    ]

    if current_master.service_center_id:
        filters.append(
            LeadSource.service_center_id == current_master.service_center_id
        )

    return or_(*filters)



def can_edit_source(source: LeadSource, current_master: Master) -> bool:
    """
    Редактировать источник может:
    - владелец-мастер;
    - администратор того же сервис-центра.
    """
    if source.master_id == current_master.id:
        return True

    if (
        current_master.is_admin == 1
        and current_master.service_center_id is not None
        and source.service_center_id == current_master.service_center_id
    ):
        return True

    return False



@router.get("", response_model=List[LeadSourceOut])
async def get_sources(
    db: AsyncSession = Depends(get_session),
    current_master=Depends(get_current_master),
):
    """
    Получить источники, доступные текущему пользователю:
    - общие источники его сервис-центра;
    - личные источники мастера.
    """
    stmt = (
        select(LeadSource)
        .where(get_owner_filters(current_master))
        .order_by(LeadSource.name)
    )

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
    """
    Создать источник.

    Для сервиса источник принадлежит сервис-центру.
    Для мастера-одиночки источник принадлежит мастеру.
    """
    if current_master.service_center_id:
        owner_filter = (
            LeadSource.service_center_id == current_master.service_center_id,
            LeadSource.name == payload.name,
        )
    else:
        owner_filter = (
            LeadSource.master_id == current_master.id,
            LeadSource.name == payload.name,
        )

    existing = await db.execute(
        select(LeadSource).where(*owner_filter)
    )

    if existing.scalar_one_or_none():
        raise HTTPException(400, "Источник с таким именем уже существует")

    source = LeadSource(
        name=payload.name,
        code=payload.code,
        description=payload.description,
        is_active=True,
        is_advertisable=payload.is_advertisable,
        service_center_id=current_master.service_center_id,
        master_id=None if current_master.service_center_id else current_master.id,
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
    result = await db.execute(
        select(LeadSource).where(LeadSource.id == source_id)
    )
    source = result.scalar_one_or_none()


    if not source:
        raise HTTPException(404, "Источник не найдена")


    if not can_edit_source(source, current_master):
        raise HTTPException(403, "Нет прав на редактирование этого источника")


    if payload.name is not None:
        if current_master.service_center_id:
            uniqueness_filter = (
                LeadSource.service_center_id == current_master.service_center_id,
                LeadSource.name == payload.name,
                LeadSource.id != source_id,
            )
        else:
            uniqueness_filter = (
                LeadSource.master_id == current_master.id,
                LeadSource.name == payload.name,
                LeadSource.id != source_id,
            )


        existing = await db.execute(
            select(LeadSource).where(*uniqueness_filter)
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
    result = await db.execute(
        select(LeadSource).where(LeadSource.id == source_id)
    )
    source = result.scalar_one_or_none()


    if not source:
        raise HTTPException(404, "Источник не найдена")


    if not can_edit_source(source, current_master):
        raise HTTPException(403, "Нет прав на удаление")


    await db.delete(source)
    await db.commit()
    return None