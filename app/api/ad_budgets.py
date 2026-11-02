# app/api/ad_budgets.py

from datetime import date, datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_master
from app.db.models import AdBudget, LeadSource, Master
from app.db.session import get_session


router = APIRouter(prefix="/api/ad-budgets", tags=["ad_budgets"])


class AdBudgetOut(BaseModel):
    id: int
    source_id: int
    source_name: Optional[str] = None
    budget_date: date
    amount: float
    currency: str
    description: Optional[str] = None
    created_at: datetime


class AdBudgetCreate(BaseModel):
    source_id: int
    budget_date: date
    amount: float
    description: Optional[str] = None
    currency: str = "RUB"


class AdBudgetUpdate(BaseModel):
    source_id: Optional[int] = None
    budget_date: Optional[date] = None
    amount: Optional[float] = None
    description: Optional[str] = None


async def get_accessible_source_ids(
    db: AsyncSession,
    current_master: Master,
) -> List[int]:
    if current_master.is_admin == 1 and current_master.service_center_id:
        result = await db.execute(
            select(LeadSource.id).where(
                LeadSource.service_center_id
                == current_master.service_center_id
            )
        )
    else:
        result = await db.execute(
            select(LeadSource.id).where(
                LeadSource.master_id == current_master.id
            )
        )

    return [row[0] for row in result.all()]


async def can_manage_source(
    db: AsyncSession,
    source: LeadSource,
    current_master: Master,
) -> bool:
    if source.master_id == current_master.id:
        return True

    if (
        current_master.is_admin == 1
        and current_master.service_center_id is not None
        and source.service_center_id == current_master.service_center_id
    ):
        return True

    return False


def serialize_budget(budget: AdBudget) -> AdBudgetOut:
    return AdBudgetOut(
        id=budget.id,
        source_id=budget.source_id,
        source_name=(
            budget.source.name if budget.source else None
        ),
        budget_date=budget.budget_date,
        amount=float(budget.amount),
        currency=budget.currency,
        description=budget.description,
        created_at=budget.created_at,
    )


@router.get("", response_model=List[AdBudgetOut])
async def get_budgets(
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    source_id: Optional[int] = None,
    db: AsyncSession = Depends(get_session),
    current_master: Master = Depends(get_current_master),
):
    accessible_source_ids = await get_accessible_source_ids(
        db,
        current_master,
    )

    if not accessible_source_ids:
        return []

    stmt = (
        select(AdBudget)
        .options(selectinload(AdBudget.source))
        .where(
            AdBudget.source_id.in_(accessible_source_ids)
        )
    )

    if date_from:
        stmt = stmt.where(
            AdBudget.budget_date >= date_from
        )

    if date_to:
        stmt = stmt.where(
            AdBudget.budget_date <= date_to
        )

    if source_id:
        stmt = stmt.where(
            AdBudget.source_id == source_id
        )

    stmt = stmt.order_by(
        AdBudget.budget_date.desc(),
        AdBudget.id.desc(),
    )

    result = await db.execute(stmt)

    return [
        serialize_budget(budget)
        for budget in result.scalars().unique().all()
    ]


@router.post(
    "",
    response_model=AdBudgetOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_budget(
    payload: AdBudgetCreate,
    db: AsyncSession = Depends(get_session),
    current_master: Master = Depends(get_current_master),
):
    result = await db.execute(
        select(LeadSource).where(
            LeadSource.id == payload.source_id
        )
    )
    source = result.scalar_one_or_none()

    if not source:
        raise HTTPException(
            status_code=404,
            detail="Источник не найден",
        )

    if not await can_manage_source(
        db,
        source,
        current_master,
    ):
        raise HTTPException(
            status_code=403,
            detail="Нет прав для этого источника",
        )

    if not source.is_advertisable:
        raise HTTPException(
            status_code=400,
            detail="Источник не помечен как рекламный",
        )

    if payload.amount <= 0:
        raise HTTPException(
            status_code=400,
            detail="Сумма должна быть больше нуля",
        )

    existing_result = await db.execute(
        select(AdBudget).where(
            AdBudget.source_id == payload.source_id,
            AdBudget.budget_date == payload.budget_date,
        )
    )

    if existing_result.scalar_one_or_none():
        raise HTTPException(
            status_code=400,
            detail="Расход на эту дату уже существует",
        )

    budget = AdBudget(
        source_id=payload.source_id,
        budget_date=payload.budget_date,
        amount=payload.amount,
        currency=payload.currency,
        description=payload.description,
    )

    db.add(budget)
    await db.commit()
    await db.refresh(budget)

    await db.refresh(budget, ["source"])

    return serialize_budget(budget)


@router.patch("/{budget_id}", response_model=AdBudgetOut)
async def update_budget(
    budget_id: int,
    payload: AdBudgetUpdate,
    db: AsyncSession = Depends(get_session),
    current_master: Master = Depends(get_current_master),
):
    result = await db.execute(
        select(AdBudget)
        .options(selectinload(AdBudget.source))
        .where(AdBudget.id == budget_id)
    )
    budget = result.scalar_one_or_none()

    if not budget:
        raise HTTPException(
            status_code=404,
            detail="Расход не найден",
        )

    if not await can_manage_source(
        db,
        budget.source,
        current_master,
    ):
        raise HTTPException(
            status_code=403,
            detail="Нет прав",
        )

    if payload.source_id is not None and payload.source_id != budget.source_id:
        new_source_result = await db.execute(
            select(LeadSource).where(
                LeadSource.id == payload.source_id
            )
        )
        new_source = new_source_result.scalar_one_or_none()

        if not new_source:
            raise HTTPException(
                status_code=404,
                detail="Новый источник не найден",
            )

        if not await can_manage_source(
            db,
            new_source,
            current_master,
        ):
            raise HTTPException(
                status_code=403,
                detail="Нет прав для нового источника",
            )

        if not new_source.is_advertisable:
            raise HTTPException(
                status_code=400,
                detail="Источник не помечен как рекламный",
            )

        budget.source_id = payload.source_id

    if payload.budget_date is not None:
        if payload.budget_date != budget.budget_date:
            existing_result = await db.execute(
                select(AdBudget).where(
                    AdBudget.source_id == budget.source_id,
                    AdBudget.budget_date
                    == payload.budget_date,
                    AdBudget.id != budget_id,
                )
            )

            if existing_result.scalar_one_or_none():
                raise HTTPException(
                    status_code=400,
                    detail="Расход на эту дату уже существует",
                )

        budget.budget_date = payload.budget_date

    if payload.amount is not None:
        if payload.amount <= 0:
            raise HTTPException(
                status_code=400,
                detail="Сумма должна быть больше нуля",
            )

        budget.amount = payload.amount

    if payload.description is not None:
        budget.description = payload.description

    await db.commit()
    await db.refresh(budget)
    await db.refresh(budget, ["source"])

    return serialize_budget(budget)


@router.delete("/{budget_id}")
async def delete_budget(
    budget_id: int,
    db: AsyncSession = Depends(get_session),
    current_master: Master = Depends(get_current_master),
):
    result = await db.execute(
        select(AdBudget)
        .options(selectinload(AdBudget.source))
        .where(AdBudget.id == budget_id)
    )
    budget = result.scalar_one_or_none()

    if not budget:
        raise HTTPException(
            status_code=404,
            detail="Расход не найден",
        )

    if not await can_manage_source(
        db,
        budget.source,
        current_master,
    ):
        raise HTTPException(
            status_code=403,
            detail="Нет прав",
        )

    await db.delete(budget)
    await db.commit()

    return {"success": True}