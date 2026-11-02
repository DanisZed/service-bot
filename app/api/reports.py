# app/api/reports.py
# Сводный отчёт: склад, финансы периода и результаты мастеров.


from datetime import date
from decimal import Decimal


from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession


from app.api.deps import get_current_master, get_db
from app.db.models import Master
from app.schemas.reports import ReportSummaryOut
from app.services.report_service import build_report_summary




router = APIRouter(prefix="/api/reports", tags=["reports"])




@router.get("/summary", response_model=ReportSummaryOut)
async def get_report_summary(
    date_from: date = Query(
        default=None,
        description="Начало периода",
    ),
    date_to: date = Query(
        default=None,
        description="Конец периода",
    ),
    dispatcher_percent: float = Query(
        default=10,
        ge=0,
        le=100,
        description="Процент диспетчера от маржи мастера",
    ),
    db: AsyncSession = Depends(get_db),
    current_master: Master = Depends(get_current_master),
):
    if date_from is None:
        today = date.today()
        date_from = today.replace(day=1)


    if date_to is None:
        date_to = date.today()


    if date_from > date_to:
        raise ValueError("Дата начала не может быть позже даты окончания")


    return await build_report_summary(
        db=db,
        current_master=current_master,
        date_from=date_from,
        date_to=date_to,
        dispatcher_percent=Decimal(str(dispatcher_percent)),
    )