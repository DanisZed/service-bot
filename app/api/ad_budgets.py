from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import List, Optional
from datetime import date, datetime
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.session import get_session
from app.db.models import AdBudget, LeadSource, Master
from app.api.deps import get_current_master

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


@router.get("", response_model=List[AdBudgetOut])
async def get_budgets(
    db: AsyncSession = Depends(get_session),
    current_master=Depends(get_current_master),
):
    """Получить все расходы текущего мастера/сервиса"""
    if current_master.is_admin == 1:
        # Администратор видит бюджеты источников всех мастеров своего сервис-центра
        if not current_master.service_center:
            return []
        # Находим всех мастеров этого сервис-центра
        masters_result = await db.execute(
            select(Master.id).where(Master.service_center_id == current_master.service_center.id)
        )
        master_ids = [row[0] for row in masters_result.all()]
        if not master_ids:
            return []
        stmt = (
            select(AdBudget)
            .join(LeadSource, AdBudget.source_id == LeadSource.id)
            .where(LeadSource.master_id.in_(master_ids))
            .order_by(AdBudget.budget_date.desc())
        )
    else:
        # Обычный мастер – только свои источники
        stmt = (
            select(AdBudget)
            .join(LeadSource, AdBudget.source_id == LeadSource.id)
            .where(LeadSource.master_id == current_master.id)
            .order_by(AdBudget.budget_date.desc())
        )
    
    result = await db.execute(stmt)
    budgets = result.scalars().all()
    
    # Подгружаем имена источников (можно одним запросом, но для простоты оставим так)
    output = []
    for b in budgets:
        source_result = await db.execute(select(LeadSource).where(LeadSource.id == b.source_id))
        source = source_result.scalar_one_or_none()
        output.append(
            AdBudgetOut(
                id=b.id,
                source_id=b.source_id,
                source_name=source.name if source else None,
                budget_date=b.budget_date,
                amount=b.amount,
                currency=b.currency,
                description=b.description,
                created_at=b.created_at,
            )
        )
    return output


@router.post("", response_model=AdBudgetOut, status_code=status.HTTP_201_CREATED)
async def create_budget(
    payload: AdBudgetCreate,
    db: AsyncSession = Depends(get_session),
    current_master=Depends(get_current_master),
):
    # Проверяем существование источника
    result = await db.execute(select(LeadSource).where(LeadSource.id == payload.source_id))
    source = result.scalar_one_or_none()
    if not source:
        raise HTTPException(404, "Источник не найден")
    
    # Проверка прав: мастер может создать бюджет только для своего источника;
    # администратор – для любого источника мастера своего сервис-центра.
    if current_master.is_admin == 1:
        if not current_master.service_center:
            raise HTTPException(403, "У администратора нет сервис-центра")
        # Проверяем, что источник принадлежит мастеру из того же сервис-центра
        master = await db.get(Master, source.master_id)
        if not master or master.service_center_id != current_master.service_center.id:
            raise HTTPException(403, "Нет прав для этого источника")
    else:
        if source.master_id != current_master.id:
            raise HTTPException(403, "Нет прав для этого источника")
    
    if not source.is_advertisable:
        raise HTTPException(400, "Источник не помечен как рекламируемый")
    
    # Проверка уникальности
    existing = await db.execute(
        select(AdBudget).where(
            AdBudget.source_id == payload.source_id,
            AdBudget.budget_date == payload.budget_date,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(400, "Расход на эту дату уже существует")
    
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
    budget = await db.get(AdBudget, budget_id)
    if not budget:
        raise HTTPException(404, "Расход не найден")
    
    # Проверяем права через источник
    source = await db.get(LeadSource, budget.source_id)
    if not source:
        raise HTTPException(404, "Источник не найден")
    
    if current_master.is_admin == 1:
        if not current_master.service_center:
            raise HTTPException(403, "У администратора нет сервис-центра")
        master = await db.get(Master, source.master_id)
        if not master or master.service_center_id != current_master.service_center.id:
            raise HTTPException(403, "Нет прав")
    else:
        if source.master_id != current_master.id:
            raise HTTPException(403, "Нет прав")
    
    # Если меняется источник – проверяем новый
    if payload.source_id is not None and payload.source_id != budget.source_id:
        new_source = await db.get(LeadSource, payload.source_id)
        if not new_source:
            raise HTTPException(404, "Новый источник не найден")
        if not new_source.is_advertisable:
            raise HTTPException(400, "Источник не помечен как рекламируемый")
        if current_master.is_admin == 1:
            if not current_master.service_center:
                raise HTTPException(403, "Нет сервис-центра")
            new_master = await db.get(Master, new_source.master_id)
            if not new_master or new_master.service_center_id != current_master.service_center.id:
                raise HTTPException(403, "Нет прав для нового источника")
        else:
            if new_source.master_id != current_master.id:
                raise HTTPException(403, "Нет прав для нового источника")
        budget.source_id = payload.source_id
    
    if payload.budget_date is not None:
        # Проверка уникальности при смене даты
        if payload.budget_date != budget.budget_date:
            existing = await db.execute(
                select(AdBudget).where(
                    AdBudget.source_id == budget.source_id,
                    AdBudget.budget_date == payload.budget_date,
                    AdBudget.id != budget_id,
                )
            )
            if existing.scalar_one_or_none():
                raise HTTPException(400, "Расход на эту дату уже существует")
        budget.budget_date = payload.budget_date
    if payload.amount is not None:
        budget.amount = payload.amount
    if payload.description is not None:
        budget.description = payload.description
    
    await db.commit()
    await db.refresh(budget)
    
    final_source = await db.get(LeadSource, budget.source_id)
    return AdBudgetOut(
        id=budget.id,
        source_id=budget.source_id,
        source_name=final_source.name if final_source else None,
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
    budget = await db.get(AdBudget, budget_id)
    if not budget:
        raise HTTPException(404, "Расход не найден")
    
    source = await db.get(LeadSource, budget.source_id)
    if source:
        if current_master.is_admin == 1:
            if not current_master.service_center:
                raise HTTPException(403, "У администратора нет сервис-центра")
            master = await db.get(Master, source.master_id)
            if not master or master.service_center_id != current_master.service_center.id:
                raise HTTPException(403, "Нет прав")
        else:
            if source.master_id != current_master.id:
                raise HTTPException(403, "Нет прав")
    
    await db.delete(budget)
    await db.commit()
    return {"success": True}