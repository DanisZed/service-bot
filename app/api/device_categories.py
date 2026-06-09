from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.db.models import DeviceCategory, Master
from app.api.deps import get_current_master

router = APIRouter(prefix="/api/device-categories", tags=["device_categories"])


class DeviceCategoryOut(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    sort_order: int
    is_active: bool


class DeviceCategoryCreate(BaseModel):
    name: str
    description: Optional[str] = None
    sort_order: int = 0


class DeviceCategoryUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    sort_order: Optional[int] = None
    is_active: Optional[bool] = None


@router.get("", response_model=List[DeviceCategoryOut])
async def get_categories(
    db: AsyncSession = Depends(get_session),
    current_master: Master = Depends(get_current_master),
):
    """Получить список категорий устройств для текущего мастера/админа"""
    
    if current_master.is_admin == 1:
        # Админ видит категории своего сервис-центра (по service_id)
        if not current_master.service_center:
            return []
        stmt = select(DeviceCategory).where(
            DeviceCategory.service_id == current_master.service_center.service_id,
            DeviceCategory.is_active == True
        ).order_by(DeviceCategory.sort_order, DeviceCategory.name)
    else:
        # Обычный мастер видит свои личные категории
        stmt = select(DeviceCategory).where(
            DeviceCategory.master_id == current_master.id,
            DeviceCategory.is_active == True
        ).order_by(DeviceCategory.sort_order, DeviceCategory.name)
    
    result = await db.execute(stmt)
    categories = result.scalars().all()
    
    return [
        DeviceCategoryOut(
            id=c.id,
            name=c.name,
            description=c.description,
            sort_order=c.sort_order,
            is_active=c.is_active,
        )
        for c in categories
    ]


@router.post("", response_model=DeviceCategoryOut, status_code=status.HTTP_201_CREATED)
async def create_category(
    payload: DeviceCategoryCreate,
    db: AsyncSession = Depends(get_session),
    current_master: Master = Depends(get_current_master),
):
    """Создать новую категорию (только для админа сервиса или мастера)"""
    
    if current_master.is_admin == 1:
        if not current_master.service_center:
            raise HTTPException(status_code=400, detail="У администратора нет сервис-центра")
        service_id = current_master.service_center.service_id
        master_id = None
    else:
        service_id = None
        master_id = current_master.id
    
    category = DeviceCategory(
        name=payload.name,
        description=payload.description,
        sort_order=payload.sort_order,
        is_active=True,
        service_id=service_id,
        master_id=master_id,
    )
    db.add(category)
    await db.commit()
    await db.refresh(category)
    
    return DeviceCategoryOut(
        id=category.id,
        name=category.name,
        description=category.description,
        sort_order=category.sort_order,
        is_active=category.is_active,
    )


@router.patch("/{category_id}", response_model=DeviceCategoryOut)
async def update_category(
    category_id: int,
    payload: DeviceCategoryUpdate,
    db: AsyncSession = Depends(get_session),
    current_master: Master = Depends(get_current_master),
):
    """Обновить категорию (только владелец или админ сервиса)"""
    
    result = await db.execute(select(DeviceCategory).where(DeviceCategory.id == category_id))
    category = result.scalar_one_or_none()
    if not category:
        raise HTTPException(status_code=404, detail="Категория не найдена")
    
    # Проверка прав
    if current_master.is_admin == 1:
        if not current_master.service_center or category.service_id != current_master.service_center.service_id:
            raise HTTPException(status_code=403, detail="Нет прав на редактирование")
    else:
        if category.master_id != current_master.id:
            raise HTTPException(status_code=403, detail="Нет прав на редактирование")
    
    if payload.name is not None:
        category.name = payload.name
    if payload.description is not None:
        category.description = payload.description
    if payload.sort_order is not None:
        category.sort_order = payload.sort_order
    if payload.is_active is not None:
        category.is_active = payload.is_active
    
    await db.commit()
    await db.refresh(category)
    
    return DeviceCategoryOut(
        id=category.id,
        name=category.name,
        description=category.description,
        sort_order=category.sort_order,
        is_active=category.is_active,
    )


@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_category(
    category_id: int,
    db: AsyncSession = Depends(get_session),
    current_master: Master = Depends(get_current_master),
):
    """Удалить категорию (только владелец или админ сервиса)"""
    
    result = await db.execute(select(DeviceCategory).where(DeviceCategory.id == category_id))
    category = result.scalar_one_or_none()
    if not category:
        raise HTTPException(status_code=404, detail="Категория не найдена")
    
    if current_master.is_admin == 1:
        if not current_master.service_center or category.service_id != current_master.service_center.service_id:
            raise HTTPException(status_code=403, detail="Нет прав на удаление")
    else:
        if category.master_id != current_master.id:
            raise HTTPException(status_code=403, detail="Нет прав на удаление")
    
    await db.delete(category)
    await db.commit()
    return