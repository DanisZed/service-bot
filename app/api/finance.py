# app/api/finance.py
# API расходов, категорий расходов и сделок перепродажи.


from datetime import datetime
from decimal import Decimal
from typing import List, Optional


from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload


from app.api.deps import get_current_master, get_db
from app.db.models import (
    Expense,
    ExpenseCategory,
    Master,
    Part,
    PartBatch,
    ResaleDeal,
    ResaleDealPart,
)


router = APIRouter(prefix="/api/finance", tags=["finance"])



# ========== СХЕМЫ ==========


class ExpenseCategoryCreate(BaseModel):
    name: str
    parent_id: Optional[int] = None



class ExpenseCategoryOut(BaseModel):
    id: int
    name: str
    parent_id: Optional[int] = None



class ExpenseCreate(BaseModel):
    category_id: int
    amount: float
    description: Optional[str] = None
    spent_at: datetime
    resale_deal_id: Optional[int] = None



class ExpenseOut(BaseModel):
    id: int
    category_id: int
    category_name: str
    amount: float
    description: Optional[str] = None
    spent_at: datetime
    resale_deal_id: Optional[int] = None



class ResaleDealCreate(BaseModel):
    title: str
    purchase_amount: float = 0
    notes: Optional[str] = None



class ResaleDealUpdate(BaseModel):
    title: Optional[str] = None
    status: Optional[str] = None
    purchase_amount: Optional[float] = None
    sale_amount: Optional[float] = None
    notes: Optional[str] = None



class ResaleDealPartOut(BaseModel):
    id: int
    part_id: int
    part_name: str
    quantity: int
    unit_cost: float
    total_cost: float



class ResaleDealOut(BaseModel):
    id: int
    title: str
    status: str
    purchase_amount: float
    sale_amount: float
    parts_cost: float
    expenses_cost: float
    total_cost: float
    profit: float
    purchased_at: Optional[datetime] = None
    sold_at: Optional[datetime] = None
    notes: Optional[str] = None
    parts: List[ResaleDealPartOut] = []



class ResaleDealPartCreate(BaseModel):
    part_id: int
    quantity: int



# ========== КАТЕГОРИИ РАСХОДОВ ==========


@router.get("/expense-categories", response_model=List[ExpenseCategoryOut])
async def list_expense_categories(
    db: AsyncSession = Depends(get_db),
    current_master: Master = Depends(get_current_master),
):
    result = await db.execute(
        select(ExpenseCategory)
        .where(
            ExpenseCategory.master_id == current_master.id,
            ExpenseCategory.is_active == True,
        )
        .order_by(ExpenseCategory.parent_id, ExpenseCategory.name)
    )


    categories = result.scalars().all()


    return [
        ExpenseCategoryOut(
            id=category.id,
            name=category.name,
            parent_id=category.parent_id,
        )
        for category in categories
    ]



@router.post("/expense-categories", response_model=ExpenseCategoryOut, status_code=201)
async def create_expense_category(
    payload: ExpenseCategoryCreate,
    db: AsyncSession = Depends(get_db),
    current_master: Master = Depends(get_current_master),
):
    name = payload.name.strip()


    if not name:
        raise HTTPException(
            status_code=400,
            detail="Название категории обязательно"
        )


    if payload.parent_id is not None:
        parent_result = await db.execute(
            select(ExpenseCategory).where(
                ExpenseCategory.id == payload.parent_id,
                ExpenseCategory.master_id == current_master.id,
            )
        )
        parent = parent_result.scalar_one_or_none()


        if not parent:
            raise HTTPException(
                status_code=404,
                detail="Родительская категория не найдена"
            )


        if parent.parent_id is not None:
            raise HTTPException(
                status_code=400,
                detail="Подкатегория не может быть родительской категорией"
            )


    duplicate_result = await db.execute(
        select(ExpenseCategory).where(
            ExpenseCategory.master_id == current_master.id,
            ExpenseCategory.parent_id == payload.parent_id,
            func.lower(ExpenseCategory.name) == name.lower(),
        )
    )


    existing = duplicate_result.scalar_one_or_none()


    if existing:
        raise HTTPException(
            status_code=400,
            detail="Такая категория уже существует"
        )


    category = ExpenseCategory(
        master_id=current_master.id,
        parent_id=payload.parent_id,
        name=name,
    )


    db.add(category)
    await db.commit()
    await db.refresh(category)


    return ExpenseCategoryOut(
        id=category.id,
        name=category.name,
        parent_id=category.parent_id,
    )



@router.delete("/expense-categories/{category_id}")
async def delete_expense_category(
    category_id: int,
    db: AsyncSession = Depends(get_db),
    current_master: Master = Depends(get_current_master),
):
    result = await db.execute(
        select(ExpenseCategory).where(
            ExpenseCategory.id == category_id,
            ExpenseCategory.master_id == current_master.id,
        )
    )


    category = result.scalar_one_or_none()


    if not category:
        raise HTTPException(
            status_code=404,
            detail="Категория не найдена"
        )


    children_result = await db.execute(
        select(ExpenseCategory).where(
            ExpenseCategory.parent_id == category.id
        )
    )


    if children_result.scalars().first():
        raise HTTPException(
            status_code=400,
            detail="Нельзя удалить категорию, в которой есть подкатегории"
        )


    expenses_result = await db.execute(
        select(Expense).where(
            Expense.category_id == category.id
        )
    )


    if expenses_result.scalars().first():
        raise HTTPException(
            status_code=400,
            detail="Нельзя удалить категорию, в которой есть расходы"
        )


    await db.delete(category)
    await db.commit()


    return {"success": True}



# ========== РАСХОДЫ ==========


@router.get("/expenses", response_model=List[ExpenseOut])
async def list_expenses(
    db: AsyncSession = Depends(get_db),
    current_master: Master = Depends(get_current_master),
):
    result = await db.execute(
        select(Expense)
        .options(selectinload(Expense.category))
        .where(Expense.master_id == current_master.id)
        .order_by(Expense.spent_at.desc())
    )


    expenses = result.scalars().unique().all()


    return [
        ExpenseOut(
            id=expense.id,
            category_id=expense.category_id,
            category_name=expense.category.name,
            amount=float(expense.amount),
            description=expense.description,
            spent_at=expense.spent_at,
            resale_deal_id=expense.resale_deal_id,
        )
        for expense in expenses
    ]



@router.post("/expenses", response_model=ExpenseOut, status_code=201)
async def create_expense(
    payload: ExpenseCreate,
    db: AsyncSession = Depends(get_db),
    current_master: Master = Depends(get_current_master),
):
    if payload.amount <= 0:
        raise HTTPException(
            status_code=400,
            detail="Сумма расхода должна быть больше нуля"
        )


    category_result = await db.execute(
        select(ExpenseCategory).where(
            ExpenseCategory.id == payload.category_id,
            ExpenseCategory.master_id == current_master.id,
        )
    )
    category = category_result.scalar_one_or_none()


    if not category:
        raise HTTPException(
            status_code=404,
            detail="Категория расхода не найдена"
        )


    if payload.resale_deal_id:
        deal_result = await db.execute(
            select(ResaleDeal).where(
                ResaleDeal.id == payload.resale_deal_id,
                ResaleDeal.master_id == current_master.id,
            )
        )
        deal = deal_result.scalar_one_or_none()


        if not deal:
            raise HTTPException(
                status_code=404,
                detail="Сделка перепродажи не найдена"
            )


    expense = Expense(
        master_id=current_master.id,
        category_id=payload.category_id,
        resale_deal_id=payload.resale_deal_id,
        amount=Decimal(str(payload.amount)),
        description=payload.description,
        spent_at=payload.spent_at,
    )


    db.add(expense)
    await db.commit()
    await db.refresh(expense)


    return ExpenseOut(
        id=expense.id,
        category_id=expense.category_id,
        category_name=category.name,
        amount=float(expense.amount),
        description=expense.description,
        spent_at=expense.spent_at,
        resale_deal_id=expense.resale_deal_id,
    )



@router.delete("/expenses/{expense_id}", status_code=204)
async def delete_expense(
    expense_id: int,
    db: AsyncSession = Depends(get_db),
    current_master: Master = Depends(get_current_master),
):
    result = await db.execute(
        select(Expense).where(
            Expense.id == expense_id,
            Expense.master_id == current_master.id,
        )
    )


    expense = result.scalar_one_or_none()


    if not expense:
        raise HTTPException(
            status_code=404,
            detail="Расход не найден"
        )


    await db.delete(expense)
    await db.commit()



# ========== СДЕЛКИ ПЕРЕПРОДАЖИ ==========


async def get_owned_deal(
    deal_id: int,
    current_master: Master,
    db: AsyncSession,
) -> ResaleDeal:
    result = await db.execute(
        select(ResaleDeal)
        .options(
            selectinload(ResaleDeal.parts).selectinload(ResaleDealPart.part)
        )
        .where(
            ResaleDeal.id == deal_id,
            ResaleDeal.master_id == current_master.id,
        )
    )


    deal = result.scalar_one_or_none()


    if not deal:
        raise HTTPException(
            status_code=404,
            detail="Сделка не найдена"
        )


    return deal



def serialize_deal(deal: ResaleDeal, expenses_total: Decimal) -> dict:
    parts_cost = sum(
        item.total_cost for item in deal.parts
    )


    total_cost = (
        deal.purchase_amount
        + parts_cost
        + expenses_total
    )


    profit = deal.sale_amount - total_cost


    return {
        "id": deal.id,
        "title": deal.title,
        "status": deal.status,
        "purchase_amount": float(deal.purchase_amount),
        "sale_amount": float(deal.sale_amount),
        "parts_cost": float(parts_cost),
        "expenses_cost": float(expenses_total),
        "total_cost": float(total_cost),
        "profit": float(profit),
        "purchased_at": deal.purchased_at,
        "sold_at": deal.sold_at,
        "notes": deal.notes,
        "parts": [
            {
                "id": item.id,
                "part_id": item.part_id,
                "part_name": item.part.name,
                "quantity": item.quantity,
                "unit_cost": float(item.unit_cost),
                "total_cost": float(item.total_cost),
            }
            for item in deal.parts
        ],
    }



async def get_deal_expenses_total(
    deal_id: int,
    db: AsyncSession,
) -> Decimal:
    result = await db.execute(
        select(func.coalesce(func.sum(Expense.amount), 0)).where(
            Expense.resale_deal_id == deal_id
        )
    )


    return result.scalar_one()



@router.get("/resale-deals", response_model=List[ResaleDealOut])
async def list_resale_deals(
    db: AsyncSession = Depends(get_db),
    current_master: Master = Depends(get_current_master),
):
    result = await db.execute(
        select(ResaleDeal)
        .options(
            selectinload(ResaleDeal.parts).selectinload(ResaleDealPart.part)
        )
        .where(ResaleDeal.master_id == current_master.id)
        .order_by(ResaleDeal.created_at.desc())
    )


    deals = result.scalars().unique().all()


    serialized = []


    for deal in deals:
        expenses_total = await get_deal_expenses_total(deal.id, db)
        serialized.append(serialize_deal(deal, expenses_total))


    return serialized



@router.post("/resale-deals", response_model=ResaleDealOut, status_code=201)
async def create_resale_deal(
    payload: ResaleDealCreate,
    db: AsyncSession = Depends(get_db),
    current_master: Master = Depends(get_current_master),
):
    title = payload.title.strip()


    if not title:
        raise HTTPException(
            status_code=400,
            detail="Укажите название сделки"
        )


    deal = ResaleDeal(
        master_id=current_master.id,
        title=title,
        status="purchased",
        purchase_amount=Decimal(str(payload.purchase_amount)),
        purchased_at=datetime.utcnow(),
        notes=payload.notes,
    )


    db.add(deal)
    await db.commit()
    await db.refresh(deal)


    expenses_total = await get_deal_expenses_total(deal.id, db)


    return serialize_deal(deal, expenses_total)



@router.get("/resale-deals/{deal_id}", response_model=ResaleDealOut)
async def get_resale_deal(
    deal_id: int,
    db: AsyncSession = Depends(get_db),
    current_master: Master = Depends(get_current_master),
):
    deal = await get_owned_deal(deal_id, current_master, db)
    expenses_total = await get_deal_expenses_total(deal.id, db)


    return serialize_deal(deal, expenses_total)



@router.patch("/resale-deals/{deal_id}", response_model=ResaleDealOut)
async def update_resale_deal(
    deal_id: int,
    payload: ResaleDealUpdate,
    db: AsyncSession = Depends(get_db),
    current_master: Master = Depends(get_current_master),
):
    deal = await get_owned_deal(deal_id, current_master, db)


    if payload.title is not None:
        deal.title = payload.title.strip()


    if payload.status is not None:
        allowed_statuses = {
            "purchased",
            "in_repair",
            "ready_for_sale",
            "sold",
            "cancelled",
        }


        if payload.status not in allowed_statuses:
            raise HTTPException(
                status_code=400,
                detail="Некорректный статус сделки"
            )


        deal.status = payload.status


        if payload.status == "sold":
            deal.sold_at = datetime.utcnow()


    if payload.purchase_amount is not None:
        deal.purchase_amount = Decimal(str(payload.purchase_amount))


    if payload.sale_amount is not None:
        deal.sale_amount = Decimal(str(payload.sale_amount))


    if payload.notes is not None:
        deal.notes = payload.notes


    await db.commit()


    deal = await get_owned_deal(deal_id, current_master, db)
    expenses_total = await get_deal_expenses_total(deal.id, db)


    return serialize_deal(deal, expenses_total)



@router.delete("/resale-deals/{deal_id}", status_code=204)
async def delete_resale_deal(
    deal_id: int,
    db: AsyncSession = Depends(get_db),
    current_master: Master = Depends(get_current_master),
):
    deal = await get_owned_deal(deal_id, current_master, db)


    await db.delete(deal)
    await db.commit()



# ========== ЗАПЧАСТИ В СДЕЛКЕ ==========


@router.post(
    "/resale-deals/{deal_id}/parts",
    response_model=ResaleDealOut,
)
async def add_part_to_resale_deal(
    deal_id: int,
    payload: ResaleDealPartCreate,
    db: AsyncSession = Depends(get_db),
    current_master: Master = Depends(get_current_master),
):
    if payload.quantity <= 0:
        raise HTTPException(
            status_code=400,
            detail="Количество должно быть больше нуля"
        )


    deal = await get_owned_deal(deal_id, current_master, db)


    part_result = await db.execute(
        select(Part)
        .options(selectinload(Part.batches))
        .where(
            Part.id == payload.part_id,
            Part.master_id == current_master.id,
        )
    )
    part = part_result.scalar_one_or_none()


    if not part:
        raise HTTPException(
            status_code=404,
            detail="Запчасть не найдена"
        )


    available_quantity = sum(
        batch.quantity_remaining for batch in part.batches
    )


    if available_quantity < payload.quantity:
        raise HTTPException(
            status_code=400,
            detail=f"Недостаточно запчастей. Доступно: {available_quantity}"
        )


    remaining = payload.quantity


    for batch in part.batches:
        if remaining <= 0:
            break


        if batch.quantity_remaining <= 0:
            continue


        take = min(batch.quantity_remaining, remaining)
        remaining -= take


        item = ResaleDealPart(
            deal_id=deal.id,
            part_id=part.id,
            batch_id=batch.id,
            quantity=take,
            unit_cost=batch.purchase_price,
            total_cost=batch.purchase_price * take,
        )


        db.add(item)
        batch.quantity_remaining -= take


    await db.commit()


    deal = await get_owned_deal(deal_id, current_master, db)
    expenses_total = await get_deal_expenses_total(deal.id, db)


    return serialize_deal(deal, expenses_total)



@router.delete(
    "/resale-deals/{deal_id}/parts/{item_id}",
    status_code=204,
)
async def delete_part_from_resale_deal(
    deal_id: int,
    item_id: int,
    db: AsyncSession = Depends(get_db),
    current_master: Master = Depends(get_current_master),
):
    deal = await get_owned_deal(deal_id, current_master, db)


    result = await db.execute(
        select(ResaleDealPart)
        .options(selectinload(ResaleDealPart.batch))
        .where(
            ResaleDealPart.id == item_id,
            ResaleDealPart.deal_id == deal.id,
        )
    )


    item = result.scalar_one_or_none()


    if not item:
        raise HTTPException(
            status_code=404,
            detail="Запчасть в сделке не найдена"
        )


    if item.batch:
        item.batch.quantity_remaining += item.quantity


    await db.delete(item)
    await db.commit()