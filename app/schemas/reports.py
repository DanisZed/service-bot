# app/schemas/reports.py
# Схемы сводного отчёта: склад, финансы и работа мастеров.


from datetime import date, datetime
from typing import List, Optional


from pydantic import BaseModel




class ReportPeriod(BaseModel):
    from_date: date
    to_date: date




class InventoryItemOut(BaseModel):
    part_id: int
    category: str
    subcategory: Optional[str] = None
    name: str
    item_type: str
    quantity: int
    purchase_price: Optional[float] = None
    total_cost: float




class InventoryOut(BaseModel):
    total_positions: int
    total_units: int
    total_cost: float
    out_of_stock_positions: int
    items: List[InventoryItemOut]




class ExpenseCategoryOut(BaseModel):
    category: str
    amount: float




class AdvertisingSourceOut(BaseModel):
    source_id: int
    source_name: str
    amount: float




class DailyFinanceOut(BaseModel):
    date: date
    revenue: float
    parts_cost: float
    expenses: float
    net_profit: float




class FinanceOut(BaseModel):
    completed_requests: int
    service_revenue: float
    parts_cost: float
    resale_revenue: float
    resale_cost: float
    parts_purchases: float
    other_expenses: float
    advertising_expenses: float
    net_profit: float
    expenses_by_category: List[ExpenseCategoryOut]
    advertising_by_source: List[AdvertisingSourceOut]
    daily: List[DailyFinanceOut]




class MasterReportOut(BaseModel):
    master_id: Optional[int] = None
    master_name: str
    requests_count: int
    revenue: float
    parts_cost: float
    gross_margin: float
    dispatcher_fee: float
    net_profit: float




class ReportSummaryOut(BaseModel):
    period: ReportPeriod
    dispatcher_percent: float
    generated_at: datetime
    inventory: InventoryOut
    finance: FinanceOut
    masters: List[MasterReportOut]




class AdvertisingSourceOut(BaseModel):
    source_id: int
    source_name: str
    amount: float