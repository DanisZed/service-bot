from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.db.models import DeviceCategory, DeviceSubtype, Master
from app.api.deps import get_current_master

router = APIRouter(prefix="/api/device-categories", tags=["device_categories"])

# ==================== СХЕМЫ ====================

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

class DeviceSubtypeOut(BaseModel):
    id: int
    category_id: int
    name: str
    description: Optional[str] = None
    price: Optional[float] = None
    duration_minutes: Optional[int] = None
    sort_order: int
    is_active: bool

class DeviceSubtypeCreate(BaseModel):
    category_id: int
    name: str
    description: Optional[str] = None
    price: Optional[float] = None
    duration_minutes: Optional[int] = None
    sort_order: int = 0
    is_active: bool = True

class DeviceSubtypeUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = None
    duration_minutes: Optional[int] = None
    sort_order: Optional[int] = None
    is_active: Optional[bool] = None

# ==================== КАТЕГОРИИ ====================

@router.get("", response_model=List[DeviceCategoryOut])
async def get_categories(
    db: AsyncSession = Depends(get_session),
    current_master: Master = Depends(get_current_master),
):
    """Получить список категорий устройств (только свои или для админа – все своего сервис-центра)"""
    if current_master.is_admin == 1:
        # Администратор: видит категории всех мастеров своего сервис-центра (т.е. те, где master_id принадлежит его центру)
        # Можно через подзапрос, но для простоты покажем категории, созданные лично админом (или можно заменить на всех мастеров центра)
        # Так как у нас сейчас нет отдельной привязки категорий к сервис-центру, оставим как у мастера.
        # Если нужно, чтобы админ видел категории всех мастеров сервиса – нужно добавить поле service_center_id в категории. 
        # Пока сделаем как для обычного мастера (админ видит только свои).
        stmt = select(DeviceCategory).where(
            DeviceCategory.master_id == current_master.id,
            DeviceCategory.is_active == True
        ).order_by(DeviceCategory.sort_order, DeviceCategory.name)
    else:
        stmt = select(DeviceCategory).where(
            DeviceCategory.master_id == current_master.id,
            DeviceCategory.is_active == True
        ).order_by(DeviceCategory.sort_order, DeviceCategory.name)
    result = await db.execute(stmt)
    categories = result.scalars().all()
    return categories

@router.post("", response_model=DeviceCategoryOut, status_code=status.HTTP_201_CREATED)
async def create_category(
    payload: DeviceCategoryCreate,
    db: AsyncSession = Depends(get_session),
    current_master: Master = Depends(get_current_master),
):
    """Создать новую категорию (привязывается к текущему мастеру)"""
    category = DeviceCategory(
        name=payload.name,
        description=payload.description,
        sort_order=payload.sort_order,
        is_active=True,
        master_id=current_master.id,
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
    result = await db.execute(select(DeviceCategory).where(DeviceCategory.id == category_id))
    category = result.scalar_one_or_none()
    if not category:
        raise HTTPException(404, "Категория не найдена")
    if category.master_id != current_master.id:
        raise HTTPException(403, "Нет прав на редактирование")
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
    result = await db.execute(select(DeviceCategory).where(DeviceCategory.id == category_id))
    category = result.scalar_one_or_none()
    if not category:
        raise HTTPException(404, "Категория не найдена")
    if category.master_id != current_master.id:
        raise HTTPException(403, "Нет прав на удаление")
    await db.delete(category)
    await db.commit()
    return

# ==================== ПОДКАТЕГОРИИ ====================

@router.post("/subtypes", response_model=DeviceSubtypeOut, status_code=status.HTTP_201_CREATED)
async def create_subtype(
    payload: DeviceSubtypeCreate,
    db: AsyncSession = Depends(get_session),
    current_master: Master = Depends(get_current_master),
):
    """Создать подкатегорию (категория указывается в поле category_id)"""
    # Проверяем существование категории и права
    result = await db.execute(select(DeviceCategory).where(DeviceCategory.id == payload.category_id))
    category = result.scalar_one_or_none()
    if not category:
        raise HTTPException(404, "Категория не найдена")
    if category.master_id != current_master.id:
        raise HTTPException(403, "Нет прав на создание подкатегории в этой категории")
    subtype = DeviceSubtype(
        category_id=payload.category_id,
        name=payload.name,
        description=payload.description,
        price=payload.price,
        duration_minutes=payload.duration_minutes,
        sort_order=payload.sort_order,
        is_active=payload.is_active,
        master_id=current_master.id,
    )
    db.add(subtype)
    await db.commit()
    await db.refresh(subtype)
    return subtype

@router.get("/{category_id}/subtypes", response_model=List[DeviceSubtypeOut])
async def get_subtypes(
    category_id: int,
    db: AsyncSession = Depends(get_session),
    current_master: Master = Depends(get_current_master),
):
    """Получить все подкатегории указанной категории"""
    result = await db.execute(
        select(DeviceSubtype)
        .where(
            DeviceSubtype.category_id == category_id,
            DeviceSubtype.master_id == current_master.id,
            DeviceSubtype.is_active == True
        )
        .order_by(DeviceSubtype.sort_order)
    )
    subtypes = result.scalars().all()
    return subtypes

@router.patch("/subtypes/{subtype_id}", response_model=DeviceSubtypeOut)
async def update_subtype(
    subtype_id: int,
    payload: DeviceSubtypeUpdate,
    db: AsyncSession = Depends(get_session),
    current_master: Master = Depends(get_current_master),
):
    result = await db.execute(select(DeviceSubtype).where(DeviceSubtype.id == subtype_id))
    subtype = result.scalar_one_or_none()
    if not subtype:
        raise HTTPException(404, "Подкатегория не найдена")
    if subtype.master_id != current_master.id:
        raise HTTPException(403, "Нет прав на редактирование")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(subtype, field, value)
    await db.commit()
    await db.refresh(subtype)
    return subtype

@router.delete("/subtypes/{subtype_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_subtype(
    subtype_id: int,
    db: AsyncSession = Depends(get_session),
    current_master: Master = Depends(get_current_master),
):
    result = await db.execute(select(DeviceSubtype).where(DeviceSubtype.id == subtype_id))
    subtype = result.scalar_one_or_none()
    if not subtype:
        raise HTTPException(404, "Подкатегория не найдена")
    if subtype.master_id != current_master.id:
        raise HTTPException(403, "Нет прав на удаление")
    await db.delete(subtype)
    await db.commit()
    return