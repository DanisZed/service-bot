# app/api/device_categories.py
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import List, Optional
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.db.models import DeviceCategory, DeviceSubtype
from app.api.deps import get_current_master

router = APIRouter(prefix="/api/device-categories", tags=["device_categories"])


# ========== СХЕМЫ ==========

class DeviceSubtypeOut(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    price: Optional[float] = None
    duration_minutes: Optional[int] = None
    is_active: bool


class DeviceCategoryOut(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    sort_order: int
    is_active: bool
    subtypes: List[DeviceSubtypeOut] = []


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


class DeviceSubtypeUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = None
    duration_minutes: Optional[int] = None
    is_active: Optional[bool] = None


# ========== ЭНДПОИНТЫ ДЛЯ КАТЕГОРИЙ ==========

@router.get("", response_model=List[DeviceCategoryOut])
async def get_categories(
    db: AsyncSession = Depends(get_session),
    current_master=Depends(get_current_master),
):
    """Получить все категории (общие + личные) с подкатегориями"""
    # Определяем условие: либо service_id, либо master_id
    if current_master.is_admin == 1 and current_master.service_id:
        stmt = select(DeviceCategory).where(
            DeviceCategory.service_id == current_master.service_id
        ).order_by(DeviceCategory.sort_order)
    else:
        stmt = select(DeviceCategory).where(
            DeviceCategory.master_id == current_master.id
        ).order_by(DeviceCategory.sort_order)
    
    result = await db.execute(stmt)
    categories = result.scalars().all()
    
    # Для каждой категории загружаем подкатегории отдельным запросом
    output = []
    for category in categories:
        subtypes_stmt = select(DeviceSubtype).where(
            DeviceSubtype.category_id == category.id,
            DeviceSubtype.is_active == True
        ).order_by(DeviceSubtype.sort_order)
        subtypes_result = await db.execute(subtypes_stmt)
        subtypes = subtypes_result.scalars().all()
        
        output.append(DeviceCategoryOut(
            id=category.id,
            name=category.name,
            description=category.description,
            sort_order=category.sort_order,
            is_active=category.is_active,
            subtypes=[
                DeviceSubtypeOut(
                    id=s.id,
                    name=s.name,
                    description=s.description,
                    price=s.price,
                    duration_minutes=s.duration_minutes,
                    is_active=s.is_active
                ) for s in subtypes
            ]
        ))
    
    return output


@router.post("", response_model=DeviceCategoryOut)
async def create_category(
    payload: DeviceCategoryCreate,
    db: AsyncSession = Depends(get_session),
    current_master=Depends(get_current_master),
):
    """Создать новую категорию"""
    category = DeviceCategory(
        name=payload.name,
        description=payload.description,
        sort_order=payload.sort_order,
        is_active=True,
        service_id=current_master.service_id if current_master.is_admin == 1 else None,
        master_id=current_master.id if current_master.is_admin == 0 else None,
    )
    db.add(category)
    await db.commit()
    await db.refresh(category)
    
    # Возвращаем без подкатегорий
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
    current_master=Depends(get_current_master),
):
    """Обновить категорию"""
    result = await db.execute(select(DeviceCategory).where(DeviceCategory.id == category_id))
    category = result.scalar_one_or_none()
    
    if not category:
        raise HTTPException(status_code=404, detail="Категория не найдена")
    
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
    
    # Загружаем подкатегории
    subtypes_stmt = select(DeviceSubtype).where(
        DeviceSubtype.category_id == category.id,
        DeviceSubtype.is_active == True
    ).order_by(DeviceSubtype.sort_order)
    subtypes_result = await db.execute(subtypes_stmt)
    subtypes = subtypes_result.scalars().all()
    
    return DeviceCategoryOut(
        id=category.id,
        name=category.name,
        description=category.description,
        sort_order=category.sort_order,
        is_active=category.is_active,
        subtypes=[
            DeviceSubtypeOut(
                id=s.id,
                name=s.name,
                description=s.description,
                price=s.price,
                duration_minutes=s.duration_minutes,
                is_active=s.is_active
            ) for s in subtypes
        ]
    )


@router.delete("/{category_id}")
async def delete_category(
    category_id: int,
    db: AsyncSession = Depends(get_session),
    current_master=Depends(get_current_master),
):
    """Удалить категорию (и все связанные подкатегории)"""
    result = await db.execute(select(DeviceCategory).where(DeviceCategory.id == category_id))
    category = result.scalar_one_or_none()
    
    if not category:
        raise HTTPException(status_code=404, detail="Категория не найдена")
    
    await db.delete(category)
    await db.commit()
    
    return {"success": True}


# ========== ЭНДПОИНТЫ ДЛЯ ПОДКАТЕГОРИЙ ==========

@router.post("/subtypes", response_model=DeviceSubtypeOut)
async def create_subtype(
    payload: DeviceSubtypeCreate,
    db: AsyncSession = Depends(get_session),
    current_master=Depends(get_current_master),
):
    """Создать новую подкатегорию (вид техники)"""
    # Проверяем, существует ли категория
    result = await db.execute(select(DeviceCategory).where(DeviceCategory.id == payload.category_id))
    category = result.scalar_one_or_none()
    
    if not category:
        raise HTTPException(status_code=404, detail="Категория не найдена")
    
    subtype = DeviceSubtype(
        category_id=payload.category_id,
        name=payload.name,
        description=payload.description,
        price=payload.price,
        duration_minutes=payload.duration_minutes,
        is_active=True,
        service_id=current_master.service_id if current_master.is_admin == 1 else None,
        master_id=current_master.id if current_master.is_admin == 0 else None,
    )
    db.add(subtype)
    await db.commit()
    await db.refresh(subtype)
    
    return DeviceSubtypeOut(
        id=subtype.id,
        name=subtype.name,
        description=subtype.description,
        price=subtype.price,
        duration_minutes=subtype.duration_minutes,
        is_active=subtype.is_active
    )


@router.patch("/subtypes/{subtype_id}", response_model=DeviceSubtypeOut)
async def update_subtype(
    subtype_id: int,
    payload: DeviceSubtypeUpdate,
    db: AsyncSession = Depends(get_session),
    current_master=Depends(get_current_master),
):
    """Обновить подкатегорию"""
    result = await db.execute(select(DeviceSubtype).where(DeviceSubtype.id == subtype_id))
    subtype = result.scalar_one_or_none()
    
    if not subtype:
        raise HTTPException(status_code=404, detail="Вид техники не найден")
    
    if payload.name is not None:
        subtype.name = payload.name
    if payload.description is not None:
        subtype.description = payload.description
    if payload.price is not None:
        subtype.price = payload.price
    if payload.duration_minutes is not None:
        subtype.duration_minutes = payload.duration_minutes
    if payload.is_active is not None:
        subtype.is_active = payload.is_active
    
    await db.commit()
    await db.refresh(subtype)
    
    return DeviceSubtypeOut(
        id=subtype.id,
        name=subtype.name,
        description=subtype.description,
        price=subtype.price,
        duration_minutes=subtype.duration_minutes,
        is_active=subtype.is_active
    )


@router.delete("/subtypes/{subtype_id}")
async def delete_subtype(
    subtype_id: int,
    db: AsyncSession = Depends(get_session),
    current_master=Depends(get_current_master),
):
    """Удалить подкатегорию"""
    result = await db.execute(select(DeviceSubtype).where(DeviceSubtype.id == subtype_id))
    subtype = result.scalar_one_or_none()
    
    if not subtype:
        raise HTTPException(status_code=404, detail="Вид техники не найден")
    
    await db.delete(subtype)
    await db.commit()
    
    return {"success": True}


@router.get("/{category_id}/subtypes", response_model=List[DeviceSubtypeOut])
async def get_subtypes_by_category(
    category_id: int,
    db: AsyncSession = Depends(get_session),
    current_master=Depends(get_current_master),
):
    """Получить все подкатегории для конкретной категории"""
    stmt = select(DeviceSubtype).where(
        DeviceSubtype.category_id == category_id,
        DeviceSubtype.is_active == True
    ).order_by(DeviceSubtype.sort_order)
    result = await db.execute(stmt)
    return result.scalars().all()