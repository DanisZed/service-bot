from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.db.models import DeviceSubtype, DeviceCategory, Master
from app.api.deps import get_current_master

router = APIRouter(prefix="/api/device-categories", tags=["device-subtypes"])

# Схемы Pydantic для валидации данных
class DeviceSubtypeCreate(BaseModel):
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

class DeviceSubtypeOut(BaseModel):
    id: int
    category_id: int
    name: str
    description: Optional[str] = None
    price: Optional[float] = None
    duration_minutes: Optional[int] = None
    sort_order: int
    is_active: bool

    class Config:
        from_attributes = True

# --- Эндпоинты ---

@router.post("/{category_id}/subtypes", response_model=DeviceSubtypeOut, status_code=status.HTTP_201_CREATED)
async def create_subtype(
    category_id: int,
    subtype_data: DeviceSubtypeCreate,
    db: AsyncSession = Depends(get_db),
    current_master: Master = Depends(get_current_master),
):
    """Создает новую подкатегорию для указанной категории."""
    # 1. Проверяем, существует ли категория и принадлежит ли она текущему мастеру
    result = await db.execute(select(DeviceCategory).where(DeviceCategory.id == category_id))
    category = result.scalar_one_or_none()
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    if category.master_id != current_master.id:
        raise HTTPException(status_code=403, detail="Not enough permissions")

    # 2. Создаем новую подкатегорию
    new_subtype = DeviceSubtype(
        **subtype_data.model_dump(),
        category_id=category_id,
        master_id=current_master.id,
    )
    db.add(new_subtype)
    await db.commit()
    await db.refresh(new_subtype)
    return new_subtype

@router.get("/{category_id}/subtypes", response_model=List[DeviceSubtypeOut])
async def get_subtypes(
    category_id: int,
    db: AsyncSession = Depends(get_db),
    current_master: Master = Depends(get_current_master),
):
    """Получает список всех подкатегорий для указанной категории."""
    result = await db.execute(
        select(DeviceSubtype)
        .where(
            DeviceSubtype.category_id == category_id,
            DeviceSubtype.master_id == current_master.id
        )
        .order_by(DeviceSubtype.sort_order)
    )
    subtypes = result.scalars().all()
    return subtypes

@router.patch("/subtypes/{subtype_id}", response_model=DeviceSubtypeOut)
async def update_subtype(
    subtype_id: int,
    update_data: DeviceSubtypeUpdate,
    db: AsyncSession = Depends(get_db),
    current_master: Master = Depends(get_current_master),
):
    """Обновляет данные подкатегории."""
    result = await db.execute(select(DeviceSubtype).where(DeviceSubtype.id == subtype_id))
    subtype = result.scalar_one_or_none()
    if not subtype:
        raise HTTPException(status_code=404, detail="Subtype not found")
    if subtype.master_id != current_master.id:
        raise HTTPException(status_code=403, detail="Not enough permissions")

    for key, value in update_data.model_dump(exclude_unset=True).items():
        setattr(subtype, key, value)

    await db.commit()
    await db.refresh(subtype)
    return subtype

@router.delete("/subtypes/{subtype_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_subtype(
    subtype_id: int,
    db: AsyncSession = Depends(get_db),
    current_master: Master = Depends(get_current_master),
):
    """Удаляет подкатегорию."""
    result = await db.execute(select(DeviceSubtype).where(DeviceSubtype.id == subtype_id))
    subtype = result.scalar_one_or_none()
    if not subtype:
        raise HTTPException(status_code=404, detail="Subtype not found")
    if subtype.master_id != current_master.id:
        raise HTTPException(status_code=403, detail="Not enough permissions")

    await db.delete(subtype)
    await db.commit()
    return