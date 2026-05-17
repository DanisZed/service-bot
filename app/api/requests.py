# app/api/requests.py
from datetime import datetime, date
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ServiceRequest
from app.api.deps import get_current_master, get_db

router = APIRouter(prefix="/api/requests", tags=["requests"])


class ServiceRequestOut(BaseModel):
    id: int

    # Время создания и статус заявки
    created_at: datetime
    status: str

    # Привязка к мастеру
    master_id: Optional[int] = None
    master_seq: int | None = None

    # Клиент
    client_id: Optional[int] = None
    client_name: Optional[str] = None
    client_phone: Optional[str] = None

    # Техника и услуга
    main_category: str
    subtype: str
    custom_device: Optional[str] = None
    service_title: Optional[str] = None

    # Адрес
    location_type: str
    address: Optional[str] = None
    address_details: Optional[str] = None

    # Описание поломки
    problem_description: str

    # Дата/время выезда
    date_iso: Optional[date] = None
    time_slot: Optional[str] = None
    datetime_from: Optional[datetime] = None
    datetime_to: Optional[datetime] = None

    # Деньги
    total_amount: Optional[float] = None
    currency: str
    payment_status: str
    paid_amount: Optional[float] = None
    paid_at: Optional[datetime] = None

    # Источник и внешние ссылки
    source: str
    yandex_url: Optional[str] = None
    google_url: Optional[str] = None

    class Config:
        from_attributes = True  # Pydantic v2


class ServiceRequestUpdate(BaseModel):
    # Что можно редактировать из фронта
    status: Optional[str] = None
    master_id: Optional[int] = None

    # Финансовая часть (под CRM)
    total_amount: Optional[float] = None
    payment_status: Optional[str] = None
    paid_amount: Optional[float] = None
    paid_at: Optional[datetime] = None


@router.get("", response_model=List[ServiceRequestOut])
async def list_requests(
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_master=Depends(get_current_master),
):
    """
    Список заявок для текущего мастера.
    Если передан ?status=..., фильтруем по нему.
    """
    stmt = (
        select(ServiceRequest)
        .where(ServiceRequest.master_id == current_master.id)
        .order_by(ServiceRequest.id.desc())
    )

    if status:
        stmt = stmt.where(ServiceRequest.status == status)

    result = await db.execute(stmt)
    rows = result.scalars().all()
    return rows


@router.get("/{request_id}", response_model=ServiceRequestOut)
async def get_request(
    request_id: int,
    db: AsyncSession = Depends(get_db),
    current_master=Depends(get_current_master),
):
    req = await db.get(ServiceRequest, request_id)
    if not req or req.master_id != current_master.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Not found"
        )
    return req


@router.patch("/{request_id}", response_model=ServiceRequestOut)
async def update_service_request(
    request_id: int,
    payload: ServiceRequestUpdate,
    db: AsyncSession = Depends(get_db),
    current_master=Depends(get_current_master),
):
    # Достаём заявку и проверяем владельца
    result = await db.execute(
        select(ServiceRequest).where(ServiceRequest.id == request_id)
    )
    obj: ServiceRequest | None = result.scalar_one_or_none()
    if not obj or obj.master_id != current_master.id:
        raise HTTPException(status_code=404, detail="Request not found")

    # если пришёл статус canceled — сразу обнуляем total_amount
    if payload.status == "canceled":
        obj.total_amount = 0

    # если пришла новая сумма — обновляем
    if payload.total_amount is not None:
        obj.total_amount = payload.total_amount

    if payload.status is not None:
        obj.status = payload.status
    if payload.payment_status is not None:
        obj.payment_status = payload.payment_status
    if payload.paid_amount is not None:
        obj.paid_amount = payload.paid_amount
    if payload.paid_at is not None:
        obj.paid_at = payload.paid_at

    await db.commit()
    await db.refresh(obj)
    return obj