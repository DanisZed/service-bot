# app/api/ad_budgets.py
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import List, Optional
from datetime import date, datetime
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.db.models import AdBudget, LeadSource
from app.api.deps import get_current_master

router = APIRouter(prefix="/api/ad-budgets", tags=["ad_budgets"])


# ========== СХЕМЫ ==========

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


# ========== ЭНДПОИНТЫ ==========

@router.get("", response_model=List[AdBudgetOut])
async def get_budgets(
    db: AsyncSession = Depends(get_session),
    current_master=Depends(get_current_master),
):
    """Получить все расходы текущего мастера/сервиса"""
    # Определяем условие для фильтрации
    if current_master.is_admin == 1 and current_master.service_id:
        stmt = select(AdBudget).join(
            LeadSource, AdBudget.source_id == LeadSource.id
        ).where(
            LeadSource.service_id == current_master.service_id
        ).order_by(AdBudget.budget_date.desc())
    else:
        stmt = select(AdBudget).join(
            LeadSource, AdBudget.source_id == LeadSource.id
        ).where(
            LeadSource.master_id == current_master.id
        ).order_by(AdBudget.budget_date.desc())
    
    result = await db.execute(stmt)
    budgets = result.scalars().all()
    
    # Добавляем название источника
    output = []
    for b in budgets:
        source_result = await db.execute(select(LeadSource).where(LeadSource.id == b.source_id))
        source = source_result.scalar_one_or_none()
        output.append(AdBudgetOut(
            id=b.id,
            source_id=b.source_id,
            source_name=source.name if source else None,
            budget_date=b.budget_date,
            amount=b.amount,
            currency=b.currency,
            description=b.description,
            created_at=b.created_at,
        ))
    
    return output


@router.post("", response_model=AdBudgetOut)
async def create_budget(
    payload: AdBudgetCreate,
    db: AsyncSession = Depends(get_session),
    current_master=Depends(get_current_master),
):
    """Создать новый расход"""
    # Проверяем, существует ли источник
    result = await db.execute(select(LeadSource).where(LeadSource.id == payload.source_id))
    source = result.scalar_one_or_none()
    
    if not source:
        raise HTTPException(status_code=404, detail="Источник не найден")
    
    # Проверяем, что источник рекламируемый
    if not source.is_advertisable:
        raise HTTPException(status_code=400, detail="Источник не помечен как рекламируемый")
    
    # Проверяем уникальность (source_id + budget_date)
    existing = await db.execute(
        select(AdBudget).where(
            AdBudget.source_id == payload.source_id,
            AdBudget.budget_date == payload.budget_date
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Расход на эту дату уже существует")
    
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
    
    return AdBudgetOut(
        id=budget.id,
        source_id=budget.source_id,
        source_name=source.name,
        budget_date=budget.budget_date,
        amount=budget.amount,
        currency=budget.currency,
        description=budget.description,
        created_at=budget.created_at,
    )


@router.patch("/{budget_id}", response_model=AdBudgetOut)
async def update_budget(
    budget_id: int,
    payload: AdBudgetUpdate,
    db: AsyncSession = Depends(get_session),
    current_master=Depends(get_current_master),
):
    """Обновить расход"""
    result = await db.execute(select(AdBudget).where(AdBudget.id == budget_id))
    budget = result.scalar_one_or_none()
    
    if not budget:
        raise HTTPException(status_code=404, detail="Расход не найден")
    
    if payload.source_id is not None:
        # Проверяем новый источник
        source_result = await db.execute(select(LeadSource).where(LeadSource.id == payload.source_id))
        source = source_result.scalar_one_or_none()
        if not source:
            raise HTTPException(status_code=404, detail="Источник не найден")
        if not source.is_advertisable:
            raise HTTPException(status_code=400, detail="Источник не помечен как рекламируемый")
        budget.source_id = payload.source_id
    
    if payload.budget_date is not None:
        budget.budget_date = payload.budget_date
    if payload.amount is not None:
        budget.amount = payload.amount
    if payload.description is not None:
        budget.description = payload.description
    
    await db.commit()
    await db.refresh(budget)
    
    # Получаем имя источника
    source_result = await db.execute(select(LeadSource).where(LeadSource.id == budget.source_id))
    source = source_result.scalar_one_or_none()
    
    return AdBudgetOut(
        id=budget.id,
        source_id=budget.source_id,
        source_name=source.name if source else None,
        budget_date=budget.budget_date,
        amount=budget.amount,
        currency=budget.currency,
        description=budget.description,
        created_at=budget.created_at,
    )


@router.delete("/{budget_id}")
async def delete_budget(
    budget_id: int,
    db: AsyncSession = Depends(get_session),
    current_master=Depends(get_current_master),
):
    """Удалить расход"""
    result = await db.execute(select(AdBudget).where(AdBudget.id == budget_id))
    budget = result.scalar_one_or_none()
    
    if not budget:
        raise HTTPException(status_code=404, detail="Расход не найден")
    
    await db.delete(budget)
    await db.commit()
    
    return {"success": True}