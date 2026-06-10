from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.session import get_session
from app.db.models import DeviceCategory, DeviceSubtype, Master
from app.api.deps import get_current_master

router = APIRouter(prefix="/api/device-categories", tags=["device_categories"])

# ==================== СХЕМЫ ====================

class DeviceSubtypeOut(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    price: Optional[float] = None
    duration_minutes: Optional[int] = None
    sort_order: int
    is_active: bool

    class Config:
        from_attributes = True

class DeviceCategoryOut(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    sort_order: int
    is_active: bool
    subtypes: List[DeviceSubtypeOut] = []   # подкатегории будут здесь

    class Config:
        from_attributes = True

class DeviceCategoryCreate(BaseModel):
    name: str
    description: Optional[str] = None
    sort_order: int = 0

class DeviceCategoryUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    sort_order: Optional[int] = None
    is_active: Optional[bool] = None

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
    query = (
        select(DeviceCategory)
        .where(
            DeviceCategory.master_id == current_master.id,
            DeviceCategory.is_active == True
        )
        .order_by(DeviceCategory.sort_order, DeviceCategory.name)
        .options(selectinload(DeviceCategory.subtypes))
    )
    result = await db.execute(query)
    categories = result.unique().scalars().all()
    return categories

@router.post("", response_model=DeviceCategoryOut, status_code=status.HTTP_201_CREATED)
async def create_category(
    payload: DeviceCategoryCreate,
    db: AsyncSession = Depends(get_session),
    current_master: Master = Depends(get_current_master),
):
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
    # У новой категории подкатегорий пока нет
    return DeviceCategoryOut(
        id=category.id,
        name=category.name,
        description=category.description,
        sort_order=category.sort_order,
        is_active=category.is_active,
        subtypes=[]
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
    # Подгружаем подкатегории для ответа
    await db.refresh(category, attribute_names=["subtypes"])
    return DeviceCategoryOut(
        id=category.id,
        name=category.name,
        description=category.description,
        sort_order=category.sort_order,
        is_active=category.is_active,
        subtypes=[DeviceSubtypeOut.model_validate(s) for s in category.subtypes if s.is_active]
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
    # Проверяем категорию
    result = await db.execute(select(DeviceCategory).where(DeviceCategory.id == payload.category_id))
    category = result.scalar_one_or_none()
    if not category or category.master_id != current_master.id:
        raise HTTPException(403, "Категория не найдена или нет прав")
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

@router.patch("/subtypes/{subtype_id}", response_model=DeviceSubtypeOut)
async def update_subtype(
    subtype_id: int,
    payload: DeviceSubtypeUpdate,
    db: AsyncSession = Depends(get_session),
    current_master: Master = Depends(get_current_master),
):
    result = await db.execute(select(DeviceSubtype).where(DeviceSubtype.id == subtype_id))
    subtype = result.scalar_one_or_none()
    if not subtype or subtype.master_id != current_master.id:
        raise HTTPException(403, "Подкатегория не найдена или нет прав")
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
    if not subtype or subtype.master_id != current_master.id:
        raise HTTPException(403, "Подкатегория не найдена или нет прав")
    await db.delete(subtype)
    await db.commit()
    return