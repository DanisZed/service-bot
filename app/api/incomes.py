# app/api/incomes.py
# API доходов и справочника источников дохода.


from datetime import datetime
from decimal import Decimal
from typing import List, Optional


from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload


from app.api.deps import get_current_master, get_db
from app.db.models import Income, IncomeSource, Master, ResaleDeal


router = APIRouter(prefix="/api/finance", tags=["finance"])


# ========== СХЕМЫ ==========


class IncomeSourceCreate(BaseModel):
    name: str


class IncomeSourceUpdate(BaseModel):
    name: Optional[str] = None
    is_active: Optional[bool] = None


class IncomeSourceOut(BaseModel):
    id: int
    name: str
    is_active: bool
    incomes_count: int = 0


class IncomeCreate(BaseModel):
    amount: float
    source_id: int
    description: Optional[str] = None
    received_at: datetime
    resale_deal_id: Optional[int] = None


class IncomeOut(BaseModel):
    id: int
    amount: float
    source_id: int
    source_name: str
    description: Optional[str] = None
    received_at: datetime
    resale_deal_id: Optional[int] = None
    resale_deal_title: Optional[str] = None


# ========== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ==========


def serialize_income(income: Income) -> dict:
    return {
        "id": income.id,
        "amount": float(income.amount),
        "source_id": income.source_id,
        "source_name": income.source.name,
        "description": income.description,
        "received_at": income.received_at,
        "resale_deal_id": income.resale_deal_id,
        "resale_deal_title": (
            income.resale_deal.title if income.resale_deal else None
        ),
    }


def serialize_source(source: IncomeSource, incomes_count: int = 0) -> dict:
    return {
        "id": source.id,
        "name": source.name,
        "is_active": source.is_active,
        "incomes_count": incomes_count,
    }


async def get_owned_source(
    source_id: int,
    current_master: Master,
    db: AsyncSession,
) -> IncomeSource:
    result = await db.execute(
        select(IncomeSource).where(
            IncomeSource.id == source_id,
            IncomeSource.master_id == current_master.id,
        )
    )


    source = result.scalar_one_or_none()


    if not source:
        raise HTTPException(
            status_code=404,
            detail="Источник дохода не найден"
        )


    return source


# ========== ИСТОЧНИКИ ДОХОДА ==========


@router.get("/income-sources", response_model=List[IncomeSourceOut])
async def list_income_sources(
    include_inactive: bool = False,
    db: AsyncSession = Depends(get_db),
    current_master: Master = Depends(get_current_master),
):
    query = (
        select(IncomeSource, func.coalesce(func.count(Income.id), 0))
        .outerjoin(Income, Income.source_id == IncomeSource.id)
        .where(IncomeSource.master_id == current_master.id)
        .group_by(IncomeSource.id)
        .order_by(IncomeSource.name)
    )


    if not include_inactive:
        query = query.having(IncomeSource.is_active == True)


    result = await db.execute(query)
    rows = result.all()


    return [
        serialize_source(source, int(count))
        for source, count in rows
    ]


@router.post("/income-sources", response_model=IncomeSourceOut, status_code=201)
async def create_income_source(
    payload: IncomeSourceCreate,
    db: AsyncSession = Depends(get_db),
    current_master: Master = Depends(get_current_master),
):
    name = payload.name.strip()


    if not name:
        raise HTTPException(
            status_code=400,
            detail="Укажите название источника дохода"
        )


    duplicate_result = await db.execute(
        select(IncomeSource).where(
            IncomeSource.master_id == current_master.id,
            func.lower(IncomeSource.name) == name.lower(),
        )
    )


    existing = duplicate_result.scalar_one_or_none()


    if existing:
        raise HTTPException(
            status_code=400,
            detail="Такой источник дохода уже существует"
        )


    source = IncomeSource(
        master_id=current_master.id,
        name=name,
    )


    db.add(source)
    await db.commit()
    await db.refresh(source)


    return serialize_source(source)


@router.patch("/income-sources/{source_id}", response_model=IncomeSourceOut)
async def update_income_source(
    source_id: int,
    payload: IncomeSourceUpdate,
    db: AsyncSession = Depends(get_db),
    current_master: Master = Depends(get_current_master),
):
    source = await get_owned_source(source_id, current_master, db)


    if payload.name is not None:
        name = payload.name.strip()


        if not name:
            raise HTTPException(
                status_code=400,
                detail="Укажите название источника дохода"
            )


        duplicate_result = await db.execute(
            select(IncomeSource).where(
                IncomeSource.master_id == current_master.id,
                IncomeSource.id != source.id,
                func.lower(IncomeSource.name) == name.lower(),
            )
        )


        existing = duplicate_result.scalar_one_or_none()


        if existing:
            raise HTTPException(
                status_code=400,
                detail="Такой источник дохода уже существует"
            )


        source.name = name


    if payload.is_active is not None:
        source.is_active = payload.is_active


    await db.commit()
    await db.refresh(source)


    count_result = await db.execute(
        select(func.count(Income.id)).where(
            Income.source_id == source.id
        )
    )
    incomes_count = count_result.scalar_one()


    return serialize_source(source, int(incomes_count))


@router.delete("/income-sources/{source_id}", status_code=204)
async def delete_income_source(
    source_id: int,
    db: AsyncSession = Depends(get_db),
    current_master: Master = Depends(get_current_master),
):
    source = await get_owned_source(source_id, current_master, db)


    count_result = await db.execute(
        select(func.count(Income.id)).where(
            Income.source_id == source.id
        )
    )
    incomes_count = count_result.scalar_one()


    if incomes_count > 0:
        raise HTTPException(
            status_code=400,
            detail="Нельзя удалить источник, к которому привязаны доходы. Архивируйте его."
        )


    await db.delete(source)
    await db.commit()


# ========== ДОХОДЫ ==========


@router.get("/incomes", response_model=List[IncomeOut])
async def list_incomes(
    db: AsyncSession = Depends(get_db),
    current_master: Master = Depends(get_current_master),
):
    result = await db.execute(
        select(Income)
        .options(
            selectinload(Income.source),
            selectinload(Income.resale_deal),
        )
        .where(Income.master_id == current_master.id)
        .order_by(Income.received_at.desc())
    )


    incomes = result.scalars().unique().all()


    return [serialize_income(income) for income in incomes]


@router.post("/incomes", response_model=IncomeOut, status_code=201)
async def create_income(
    payload: IncomeCreate,
    db: AsyncSession = Depends(get_db),
    current_master: Master = Depends(get_current_master),
):
    if payload.amount <= 0:
        raise HTTPException(
            status_code=400,
            detail="Сумма дохода должна быть больше нуля"
        )


    source = await get_owned_source(payload.source_id, current_master, db)


    if not source.is_active:
        raise HTTPException(
            status_code=400,
            detail="Источник дохода архивирован"
        )


    resale_deal = None


    if payload.resale_deal_id:
        result = await db.execute(
            select(ResaleDeal).where(
                ResaleDeal.id == payload.resale_deal_id,
                ResaleDeal.master_id == current_master.id,
            )
        )
        resale_deal = result.scalar_one_or_none()


        if not resale_deal:
            raise HTTPException(
                status_code=404,
                detail="Сделка перепродажи не найдена"
            )


    income = Income(
        master_id=current_master.id,
        source_id=source.id,
        resale_deal_id=resale_deal.id if resale_deal else None,
        amount=Decimal(str(payload.amount)),
        description=payload.description,
        received_at=payload.received_at,
    )


    db.add(income)
    await db.commit()


    result = await db.execute(
        select(Income)
        .options(
            selectinload(Income.source),
            selectinload(Income.resale_deal),
        )
        .where(Income.id == income.id)
    )


    income = result.scalar_one()


    return serialize_income(income)


@router.delete("/incomes/{income_id}", status_code=204)
async def delete_income(
    income_id: int,
    db: AsyncSession = Depends(get_db),
    current_master: Master = Depends(get_current_master),
):
    result = await db.execute(
        select(Income).where(
            Income.id == income_id,
            Income.master_id == current_master.id,
        )
    )


    income = result.scalar_one_or_none()


    if not income:
        raise HTTPException(
            status_code=404,
            detail="Доход не найден"
        )


    await db.delete(income)
    await db.commit()