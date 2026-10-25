# app/api/parts.py
# API склада запчастей: список, создание, партии закупки и FIFO-списание в заявку.

from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_master, get_db
from app.db.models import Master, Part, PartBatch, RequestPart, ServiceRequest

router = APIRouter(prefix="/api/parts", tags=["parts"])


class PartOut(BaseModel):
    id: int
    category: str
    name: str
    quantity: int
    purchase_price: Optional[float] = None
    is_active: bool

    class Config:
        from_attributes = True


class PartBatchOut(BaseModel):
    id: int
    quantity_initial: int
    quantity_remaining: int
    purchase_price: float
    purchased_at: datetime
    supplier: Optional[str] = None
    comment: Optional[str] = None

    class Config:
        from_attributes = True


class PartDetailOut(PartOut):
    batches: List[PartBatchOut] = []


class PartCreate(BaseModel):
    category: str
    name: str
    quantity: int
    purchase_price: float
    supplier: Optional[str] = None
    comment: Optional[str] = None


class PartBatchCreate(BaseModel):
    quantity: int
    purchase_price: float
    supplier: Optional[str] = None
    comment: Optional[str] = None


class RequestPartOut(BaseModel):
    id: int
    part_id: int
    part_name: str
    batch_id: int
    quantity: int
    unit_cost: float
    total_cost: float
    created_at: datetime

    class Config:
        from_attributes = True


class ConsumePartPayload(BaseModel):
    part_id: int
    quantity: int


def serialize_part(part: Part) -> dict:
    total_quantity = sum(batch.quantity_remaining for batch in part.batches)
    available_batches = [batch for batch in part.batches if batch.quantity_remaining > 0]

    return {
        "id": part.id,
        "category": part.category,
        "name": part.name,
        "quantity": total_quantity,
        "purchase_price": (
            float(available_batches[0].purchase_price)
            if available_batches
            else None
        ),
        "is_active": part.is_active,
        "batches": [
            {
                "id": batch.id,
                "quantity_initial": batch.quantity_initial,
                "quantity_remaining": batch.quantity_remaining,
                "purchase_price": float(batch.purchase_price),
                "purchased_at": batch.purchased_at,
                "supplier": batch.supplier,
                "comment": batch.comment,
            }
            for batch in part.batches
        ],
    }


async def get_owned_part(
    part_id: int,
    current_master: Master,
    db: AsyncSession,
) -> Part:
    result = await db.execute(
        select(Part)
        .options(selectinload(Part.batches))
        .where(
            Part.id == part_id,
            Part.master_id == current_master.id,
        )
    )

    part = result.scalar_one_or_none()

    if not part:
        raise HTTPException(status_code=404, detail="Запчасть не найдена")

    return part


@router.get("", response_model=List[PartDetailOut])
async def list_parts(
    db: AsyncSession = Depends(get_db),
    current_master: Master = Depends(get_current_master),
):
    result = await db.execute(
        select(Part)
        .options(selectinload(Part.batches))
        .where(
            Part.master_id == current_master.id,
            Part.is_active == True,
        )
        .order_by(Part.category, Part.name)
    )

    parts = result.scalars().unique().all()

    return [serialize_part(part) for part in parts]


@router.post("", response_model=PartDetailOut, status_code=201)
async def create_part(
    payload: PartCreate,
    db: AsyncSession = Depends(get_db),
    current_master: Master = Depends(get_current_master),
):
    if payload.quantity <= 0:
        raise HTTPException(status_code=400, detail="Количество должно быть больше нуля")

    if payload.purchase_price < 0:
        raise HTTPException(status_code=400, detail="Цена не может быть отрицательной")

    part = Part(
        master_id=current_master.id,
        category=payload.category.strip(),
        name=payload.name.strip(),
    )

    db.add(part)
    await db.flush()

    batch = PartBatch(
        part_id=part.id,
        quantity_initial=payload.quantity,
        quantity_remaining=payload.quantity,
        purchase_price=Decimal(str(payload.purchase_price)),
        supplier=payload.supplier,
        comment=payload.comment,
    )

    db.add(batch)
    await db.commit()

    part = await get_owned_part(part.id, current_master, db)

    return serialize_part(part)


@router.get("/{part_id}", response_model=PartDetailOut)
async def get_part(
    part_id: int,
    db: AsyncSession = Depends(get_db),
    current_master: Master = Depends(get_current_master),
):
    part = await get_owned_part(part_id, current_master, db)
    return serialize_part(part)


@router.patch("/{part_id}", response_model=PartDetailOut)
async def update_part(
    part_id: int,
    payload: PartUpdate,
    db: AsyncSession = Depends(get_db),
    current_master: Master = Depends(get_current_master),
):
    part = await get_owned_part(part_id, current_master, db)

    if payload.category is not None:
        part.category = payload.category.strip()

    if payload.name is not None:
        part.name = payload.name.strip()

    if payload.is_active is not None:
        part.is_active = payload.is_active

    await db.commit()

    part = await get_owned_part(part_id, current_master, db)

    return serialize_part(part)


@router.post("/{part_id}/batches", response_model=PartDetailOut)
async def add_part_batch(
    part_id: int,
    payload: PartBatchCreate,
    db: AsyncSession = Depends(get_db),
    current_master: Master = Depends(get_current_master),
):
    if payload.quantity <= 0:
        raise HTTPException(status_code=400, detail="Количество должно быть больше нуля")

    if payload.purchase_price < 0:
        raise HTTPException(status_code=400, detail="Цена не может быть отрицательной")

    part = await get_owned_part(part_id, current_master, db)

    batch = PartBatch(
        part_id=part.id,
        quantity_initial=payload.quantity,
        quantity_remaining=payload.quantity,
        purchase_price=Decimal(str(payload.purchase_price)),
        supplier=payload.supplier,
        comment=payload.comment,
    )

    db.add(batch)
    await db.commit()

    part = await get_owned_part(part.id, current_master, db)

    return serialize_part(part)


@router.get("/requests/{request_id}", response_model=List[RequestPartOut])
async def list_request_parts(
    request_id: int,
    db: AsyncSession = Depends(get_db),
    current_master: Master = Depends(get_current_master),
):
    request = await db.get(ServiceRequest, request_id)

    if not request or (
        request.master_id != current_master.id
        and request.assigned_master_id != current_master.id
    ):
        raise HTTPException(status_code=404, detail="Заявка не найдена")

    result = await db.execute(
        select(RequestPart)
        .options(selectinload(RequestPart.part))
        .where(RequestPart.request_id == request_id)
        .order_by(RequestPart.created_at)
    )

    items = result.scalars().unique().all()

    return [
        {
            "id": item.id,
            "part_id": item.part_id,
            "part_name": item.part.name,
            "batch_id": item.batch_id,
            "quantity": item.quantity,
            "unit_cost": float(item.unit_cost),
            "total_cost": float(item.total_cost),
            "created_at": item.created_at,
        }
        for item in items
    ]


@router.post("/requests/{request_id}/consume", response_model=List[RequestPartOut])
async def consume_part(
    request_id: int,
    payload: ConsumePartPayload,
    db: AsyncSession = Depends(get_db),
    current_master: Master = Depends(get_current_master),
):
    request = await db.get(ServiceRequest, request_id)

    if not request or (
        request.master_id != current_master.id
        and request.assigned_master_id != current_master.id
    ):
        raise HTTPException(status_code=404, detail="Заявка не найдена")

    if payload.quantity <= 0:
        raise HTTPException(status_code=400, detail="Количество должно быть больше нуля")

    part = await get_owned_part(payload.part_id, current_master, db)

    available_quantity = sum(
        batch.quantity_remaining for batch in part.batches
    )

    if available_quantity < payload.quantity:
        raise HTTPException(
            status_code=400,
            detail=f"Недостаточно запчастей. Доступно: {available_quantity}",
        )

    remaining = payload.quantity
    created_items = []

    for batch in part.batches:
        if remaining <= 0:
            break

        if batch.quantity_remaining <= 0:
            continue

        take = min(batch.quantity_remaining, remaining)

        batch.quantity_remaining -= take
        remaining -= take

        item = RequestPart(
            request_id=request.id,
            part_id=part.id,
            batch_id=batch.id,
            quantity=take,
            unit_cost=batch.purchase_price,
            total_cost=batch.purchase_price * take,
        )

        db.add(item)
        created_items.append(item)

    await db.commit()

    for item in created_items:
        await db.refresh(item)

    return [
        {
            "id": item.id,
            "part_id": item.part_id,
            "part_name": part.name,
            "batch_id": item.batch_id,
            "quantity": item.quantity,
            "unit_cost": float(item.unit_cost),
            "total_cost": float(item.total_cost),
            "created_at": item.created_at,
        }
        for item in created_items
    ]