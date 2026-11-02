# app/services/report_service.py
# Расчёт сводного отчёта: склад, финансы периода и результаты мастеров.


from datetime import date, datetime, time, timezone
from decimal import Decimal
from typing import Dict, List


from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload


from app.db.models import (
    AdBudget,
    Expense,
    LeadSource,
    Master,
    Part,
    PartBatch,
    RequestPart,
    ResaleDeal,
    ServiceRequest,
)




def to_money(value) -> Decimal:
    if value is None:
        return Decimal("0")


    return Decimal(str(value))




def build_period_range(
    date_from: date,
    date_to: date,
) -> tuple[datetime, datetime]:
    start = datetime.combine(
        date_from,
        time.min,
        tzinfo=timezone.utc,
    )


    end = datetime.combine(
        date_to,
        time.max,
        tzinfo=timezone.utc,
    )


    return start, end




async def build_inventory(
    db: AsyncSession,
    current_master: Master,
) -> dict:
    result = await db.execute(
        select(Part)
        .options(selectinload(Part.batches))
        .where(
            Part.master_id == current_master.id,
            Part.is_active == True,
        )
        .order_by(Part.category, Part.subcategory, Part.name)
    )


    parts = result.scalars().unique().all()


    items = []
    total_positions = 0
    total_units = 0
    total_cost = Decimal("0")
    out_of_stock_positions = 0


    for part in parts:
        available_batches = [
            batch
            for batch in part.batches
            if batch.quantity_remaining > 0
        ]


        quantity = sum(
            batch.quantity_remaining
            for batch in available_batches
        )


        cost = sum(
            to_money(batch.purchase_price)
            * batch.quantity_remaining
            for batch in available_batches
        )


        total_positions += 1
        total_units += quantity
        total_cost += cost


        if quantity == 0:
            out_of_stock_positions += 1


        items.append(
            {
                "part_id": part.id,
                "category": part.category,
                "subcategory": part.subcategory,
                "name": part.name,
                "item_type": part.item_type,
                "quantity": quantity,
                "purchase_price": (
                    float(available_batches[0].purchase_price)
                    if available_batches
                    else None
                ),
                "total_cost": float(cost),
            }
        )


    return {
        "total_positions": total_positions,
        "total_units": total_units,
        "total_cost": float(total_cost),
        "out_of_stock_positions": out_of_stock_positions,
        "items": items,
    }




async def build_finance(
    db: AsyncSession,
    current_master: Master,
    date_from: date,
    date_to: date,
) -> dict:
    period_start, period_end = build_period_range(
        date_from,
        date_to,
    )


    requests_result = await db.execute(
        select(ServiceRequest)
        .where(
            ServiceRequest.master_id == current_master.id,
            ServiceRequest.status == "done",
            ServiceRequest.done_at >= period_start,
            ServiceRequest.done_at <= period_end,
        )
        .order_by(ServiceRequest.done_at)
    )


    requests = requests_result.scalars().all()
    request_ids = [request.id for request in requests]


    service_revenue = sum(
        to_money(request.total_amount)
        for request in requests
    )


    parts_cost = Decimal("0")
    parts_by_request: Dict[int, Decimal] = {}


    if request_ids:
        request_parts_result = await db.execute(
            select(RequestPart).where(
                RequestPart.request_id.in_(request_ids)
            )
        )


        request_parts = request_parts_result.scalars().all()


        for item in request_parts:
            item_cost = to_money(item.total_cost)


            parts_cost += item_cost
            parts_by_request[item.request_id] = (
                parts_by_request.get(
                    item.request_id,
                    Decimal("0"),
                )
                + item_cost
            )


    purchases_result = await db.execute(
        select(PartBatch)
        .join(Part, Part.id == PartBatch.part_id)
        .where(
            Part.master_id == current_master.id,
            PartBatch.purchased_at >= period_start,
            PartBatch.purchased_at <= period_end,
        )
    )


    purchases = purchases_result.scalars().all()


    parts_purchases = sum(
        to_money(batch.purchase_price)
        * batch.quantity_initial
        for batch in purchases
    )


    expenses_result = await db.execute(
        select(Expense)
        .options(selectinload(Expense.category))
        .where(
            Expense.master_id == current_master.id,
            Expense.spent_at >= period_start,
            Expense.spent_at <= period_end,
            Expense.resale_deal_id.is_(None),
        )
    )


    expenses = expenses_result.scalars().unique().all()


    other_expenses = sum(
        to_money(expense.amount)
        for expense in expenses
    )


    advertising_result = await db.execute(
        select(AdBudget)
        .options(selectinload(AdBudget.source))
        .join(LeadSource, LeadSource.id == AdBudget.source_id)
        .where(
            LeadSource.master_id == current_master.id,
            LeadSource.is_advertisable == True,
            AdBudget.budget_date >= date_from,
            AdBudget.budget_date <= date_to,
        )
    )


    advertising_budgets = advertising_result.scalars().unique().all()


    advertising_expenses = sum(
        to_money(budget.amount)
        for budget in advertising_budgets
    )


    advertising_by_source: Dict[int, dict] = {}


    for budget in advertising_budgets:
        source = budget.source


        if not source:
            continue


        source_id = source.id
        source_name = source.name


        if source_id not in advertising_by_source:
            advertising_by_source[source_id] = {
                "source_id": source_id,
                "source_name": source_name,
                "amount": Decimal("0"),
            }


        advertising_by_source[source_id]["amount"] += to_money(
            budget.amount
        )


    resale_result = await db.execute(
        select(ResaleDeal)
        .options(selectinload(ResaleDeal.parts))
        .where(
            ResaleDeal.master_id == current_master.id,
            ResaleDeal.status == "sold",
            ResaleDeal.sold_at >= period_start,
            ResaleDeal.sold_at <= period_end,
        )
    )


    resale_deals = resale_result.scalars().unique().all()


    resale_revenue = sum(
        to_money(deal.sale_amount)
        for deal in resale_deals
    )


    resale_cost = sum(
        to_money(deal.purchase_amount)
        + to_money(deal.delivery_cost)
        + sum(
            to_money(item.total_cost)
            for item in deal.parts
        )
        for deal in resale_deals
    )


    net_profit = (
        service_revenue
        + resale_revenue
        - parts_cost
        - resale_cost
        - other_expenses
        - advertising_expenses
    )


    expenses_by_category: Dict[str, Decimal] = {}


    for expense in expenses:
        category_name = (
            expense.category.name
            if expense.category
            else "Без категории"
        )


        expenses_by_category[category_name] = (
            expenses_by_category.get(
                category_name,
                Decimal("0"),
            )
            + to_money(expense.amount)
        )


    daily: Dict[date, dict] = {}


    for request in requests:
        day = request.done_at.date()


        day_data = daily.setdefault(
            day,
            {
                "revenue": Decimal("0"),
                "parts_cost": Decimal("0"),
                "expenses": Decimal("0"),
            },
        )


        day_data["revenue"] += to_money(request.total_amount)
        day_data["parts_cost"] += parts_by_request.get(
            request.id,
            Decimal("0"),
        )


    for expense in expenses:
        day = expense.spent_at.date()


        day_data = daily.setdefault(
            day,
            {
                "revenue": Decimal("0"),
                "parts_cost": Decimal("0"),
                "expenses": Decimal("0"),
            },
        )


        day_data["expenses"] += to_money(expense.amount)


    daily_items = []


    for day in sorted(daily.keys()):
        day_data = daily[day]


        daily_items.append(
            {
                "date": day,
                "revenue": float(day_data["revenue"]),
                "parts_cost": float(day_data["parts_cost"]),
                "expenses": float(day_data["expenses"]),
                "net_profit": float(
                    day_data["revenue"]
                    - day_data["parts_cost"]
                    - day_data["expenses"]
                ),
            }
        )


    return {
        "completed_requests": len(requests),
        "service_revenue": float(service_revenue),
        "parts_cost": float(parts_cost),
        "resale_revenue": float(resale_revenue),
        "resale_cost": float(resale_cost),
        "parts_purchases": float(parts_purchases),
        "other_expenses": float(other_expenses),
        "advertising_expenses": float(advertising_expenses),
        "net_profit": float(net_profit),
        "expenses_by_category": [
            {
                "category": category,
                "amount": float(amount),
            }
            for category, amount in sorted(
                expenses_by_category.items()
            )
        ],
        "advertising_by_source": [
            {
                "source_id": item["source_id"],
                "source_name": item["source_name"],
                "amount": float(item["amount"]),
            }
            for item in sorted(
                advertising_by_source.values(),
                key=lambda source: source["amount"],
                reverse=True,
            )
        ],
        "daily": daily_items,
    }




async def build_masters_report(
    db: AsyncSession,
    current_master: Master,
    date_from: date,
    date_to: date,
    dispatcher_percent: Decimal,
) -> List[dict]:
    period_start, period_end = build_period_range(
        date_from,
        date_to,
    )


    requests_result = await db.execute(
        select(ServiceRequest)
        .where(
            ServiceRequest.master_id == current_master.id,
            ServiceRequest.status == "done",
            ServiceRequest.done_at >= period_start,
            ServiceRequest.done_at <= period_end,
        )
    )


    requests = requests_result.scalars().all()
    request_ids = [request.id for request in requests]


    parts_by_request: Dict[int, Decimal] = {}


    if request_ids:
        request_parts_result = await db.execute(
            select(RequestPart).where(
                RequestPart.request_id.in_(request_ids)
            )
        )


        for item in request_parts_result.scalars().all():
            parts_by_request[item.request_id] = (
                parts_by_request.get(
                    item.request_id,
                    Decimal("0"),
                )
                + to_money(item.total_cost)
            )


    executor_ids = {
        request.assigned_master_id or request.master_id
        for request in requests
        if request.assigned_master_id or request.master_id
    }


    masters: Dict[int, Master] = {}


    if executor_ids:
        masters_result = await db.execute(
            select(Master).where(
                Master.id.in_(executor_ids)
            )
        )


        masters = {
            master.id: master
            for master in masters_result.scalars().all()
        }


    report: Dict[int, dict] = {}


    for request in requests:
        executor_id = (
            request.assigned_master_id or request.master_id
        )


        master = masters.get(executor_id)


        master_name = (
            " ".join(
                part
                for part in [
                    master.lastname if master else None,
                    master.name if master else None,
                ]
                if part
            )
            if master
            else "Не назначен"
        )


        item = report.setdefault(
            executor_id,
            {
                "master_id": executor_id,
                "master_name": master_name,
                "requests_count": 0,
                "revenue": Decimal("0"),
                "parts_cost": Decimal("0"),
            },
        )


        item["requests_count"] += 1
        item["revenue"] += to_money(request.total_amount)
        item["parts_cost"] += parts_by_request.get(
            request.id,
            Decimal("0"),
        )


    result = []


    for item in report.values():
        gross_margin = (
            item["revenue"] - item["parts_cost"]
        )


        dispatcher_fee = (
            gross_margin * dispatcher_percent / Decimal("100")
        )


        net_profit = gross_margin - dispatcher_fee


        result.append(
            {
                "master_id": item["master_id"],
                "master_name": item["master_name"],
                "requests_count": item["requests_count"],
                "revenue": float(item["revenue"]),
                "parts_cost": float(item["parts_cost"]),
                "gross_margin": float(gross_margin),
                "dispatcher_fee": float(dispatcher_fee),
                "net_profit": float(net_profit),
            }
        )


    result.sort(
        key=lambda item: item["revenue"],
        reverse=True,
    )


    return result




async def build_report_summary(
    db: AsyncSession,
    current_master: Master,
    date_from: date,
    date_to: date,
    dispatcher_percent: Decimal,
) -> dict:
    inventory = await build_inventory(db, current_master)


    finance = await build_finance(
        db,
        current_master,
        date_from,
        date_to,
    )


    masters = await build_masters_report(
        db,
        current_master,
        date_from,
        date_to,
        dispatcher_percent,
    )


    return {
        "period": {
            "from_date": date_from,
            "to_date": date_to,
        },
        "dispatcher_percent": float(dispatcher_percent),
        "generated_at": datetime.now(timezone.utc),
        "inventory": inventory,
        "finance": finance,
        "masters": masters,
    }