# app/api/suppliers.py
# API поставщиков запчастей и статистика поставок.

from decimal import Decimal
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_master, get_db
from app.db.models import Master, Part, PartBatch, Supplier

router = APIRouter(prefix="/api/suppliers", tags=["suppliers"])


class SupplierCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    phone: Optional[str] = None
    comment: Optional[str] = None


class SupplierUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    phone: Optional[str] = None
    comment: Optional[str] = None
    is_active: Optional[bool] = None


class SupplierOut(BaseModel):
    id: int
    name: str
    phone: Optional[str] = None
    comment: Optional[str] = None
    is_active: bool
    batches_count: int = 0
    total_quantity: int = 0
    total_amount: float = 0

    model_config = ConfigDict(from_attributes=True)


async def get_owned_supplier(
    supplier_id: int,
    current_master: Master,
    db: AsyncSession,
) -> Supplier:
    result = await db.execute(
        select(Supplier).where(
            Supplier.id == supplier_id,
            Supplier.master_id == current_master.id,
        )
    )
    supplier = result.scalar_one_or_none()

    if not supplier:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Поставщик не найден",
        )

    return supplier


def serialize_supplier(supplier: Supplier, stats: dict = None) -> dict:
    stats = stats or {}
    total_amount = stats.get("total_amount") or Decimal("0")

    return {
        "id": supplier.id,
        "name": supplier.name,
        "phone": supplier.phone,
        "comment": supplier.comment,
        "is_active": supplier.is_active,
        "batches_count": stats.get("batches_count", 0),
        "total_quantity": stats.get("total_quantity", 0),
        "total_amount": float(total_amount),
    }


@router.get("", response_model=List[SupplierOut])
async def list_suppliers(
    db: AsyncSession = Depends(get_db),
    current_master: Master = Depends(get_current_master),
):
    result = await db.execute(
        select(Supplier)
        .where(Supplier.master_id == current_master.id)
        .order_by(Supplier.name)
    )
    suppliers = result.scalars().all()

    stats_result = await db.execute(
        select(
            PartBatch.supplier_id,
            func.count(PartBatch.id).label("batches_count"),
            func.coalesce(func.sum(PartBatch.quantity_initial), 0).label("total_quantity"),
            func.coalesce(
                func.sum(PartBatch.quantity_initial * PartBatch.purchase_price),
                Decimal("0"),
            ).label("total_amount"),
        )
        .join(Part, PartBatch.part_id == Part.id)
        .where(Part.master_id == current_master.id)
        .group_by(PartBatch.supplier_id)
    )
    stats = {row.supplier_id: row._mapping for row in stats_result}

    return [
        serialize_supplier(supplier, stats.get(supplier.id))
        for supplier in suppliers
    ]


@router.post("", response_model=SupplierOut, status_code=status.HTTP_201_CREATED)
async def create_supplier(
    payload: SupplierCreate,
    db: AsyncSession = Depends(get_db),
    current_master: Master = Depends(get_current_master),
):
    supplier = Supplier(
        master_id=current_master.id,
        name=payload.name.strip(),
        phone=payload.phone,
        comment=payload.comment,
    )

    db.add(supplier)
    await db.commit()
    await db.refresh(supplier)

    return serialize_supplier(supplier)


@router.get("/{supplier_id}", response_model=SupplierOut)
async def get_supplier(
    supplier_id: int,
    db: AsyncSession = Depends(get_db),
    current_master: Master = Depends(get_current_master),
):
    supplier = await get_owned_supplier(supplier_id, current_master, db)
    return serialize_supplier(supplier)


@router.patch("/{supplier_id}", response_model=SupplierOut)
async def update_supplier(
    supplier_id: int,
    payload: SupplierUpdate,
    db: AsyncSession = Depends(get_db),
    current_master: Master = Depends(get_current_master),
):
    supplier = await get_owned_supplier(supplier_id, current_master, db)

    if payload.name is not None:
        supplier.name = payload.name.strip()
    if payload.phone is not None:
        supplier.phone = payload.phone
    if payload.comment is not None:
        supplier.comment = payload.comment
    if payload.is_active is not None:
        supplier.is_active = payload.is_active

    await db.commit()
    await db.refresh(supplier)

    return serialize_supplier(supplier)


@router.delete("/{supplier_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_supplier(
    supplier_id: int,
    db: AsyncSession = Depends(get_db),
    current_master: Master = Depends(get_current_master),
):
    supplier = await get_owned_supplier(supplier_id, current_master, db)
    supplier.is_active = False

    await db.commit()


@router.get("/{supplier_id}/batches")
async def list_supplier_batches(
    supplier_id: int,
    db: AsyncSession = Depends(get_db),
    current_master: Master = Depends(get_current_master),
):
    supplier = await get_owned_supplier(supplier_id, current_master, db)

    result = await db.execute(
        select(PartBatch)
        .options(selectinload(PartBatch.part))
        .join(Part, PartBatch.part_id == Part.id)
        .where(
            PartBatch.supplier_id == supplier.id,
            Part.master_id == current_master.id,
        )
        .order_by(PartBatch.purchased_at.desc())
    )
    batches = result.scalars().unique().all()

    return [
        {
            "id": batch.id,
            "part_id": batch.part_id,
            "part_name": batch.part.name if batch.part else "",
            "quantity_initial": batch.quantity_initial,
            "quantity_remaining": batch.quantity_remaining,
            "purchase_price": float(batch.purchase_price),
            "purchased_at": batch.purchased_at,
            "comment": batch.comment,
        }
        for batch in batches
    ]