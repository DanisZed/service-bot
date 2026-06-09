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
    what_was_done: Optional[str] = None

    # Дата/время выезда
    date_iso: Optional[date] = None
    time_slot: Optional[str] = None
    datetime_from: Optional[datetime] = None
    datetime_to: Optional[datetime] = None

    # Деньги
    total_amount: Optional[float] = None
    parts_cost: Optional[float] = None   # ← добавить
    currency: str
    payment_status: str
    paid_amount: Optional[float] = None
    paid_at: Optional[datetime] = None

    # Источник и внешние ссылки
    source: str
    yandex_url: Optional[str] = None
    google_url: Optional[str] = None
    
    # Даты статусов
    done_at: Optional[datetime] = None      # ← ДОБАВИТЬ
    cancelled_at: Optional[datetime] = None # ← ДОБАВИТЬ
    in_work_at: Optional[datetime] = None   # ← ДОБАВИТЬ

    class Config:
        from_attributes = True


class ServiceRequestUpdate(BaseModel):
    # Что можно редактировать из фронта
    status: Optional[str] = None
    master_id: Optional[int] = None

    # Финансовая часть (под CRM)
    total_amount: Optional[float] = None
    parts_cost: Optional[float] = None
    payment_status: Optional[str] = None
    paid_amount: Optional[float] = None
    paid_at: Optional[datetime] = None
    
    # Источник
    source: Optional[str] = None
    
    # Выполненные работы
    what_was_done: Optional[str] = None

    # Техника и услуга
    main_category: Optional[str] = None
    subtype: Optional[str] = None
    service_title: Optional[str] = None


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

    # ========== ОБРАБОТКА СМЕНЫ СТАТУСА С ПРОСТАНОВКОЙ ДАТ ==========
    if payload.status is not None and payload.status != obj.status:
        old_status = obj.status
        new_status = payload.status
        now = datetime.utcnow()
        
        # Если статус меняется на "in_work" (В работе)
        if new_status == "in_work" and old_status != "in_work":
            obj.in_work_at = now
        
        # Если статус меняется на "done" (Завершена)
        if new_status == "done" and old_status != "done":
            obj.done_at = now
            # Если не было отметки "в работе", ставим её тоже
            if not obj.in_work_at:
                obj.in_work_at = now
        
        # Если статус меняется на "canceled" (Отменена)
        if new_status == "canceled" and old_status != "canceled":
            obj.cancelled_at = now
            obj.total_amount = 0  # обнуляем сумму при отмене
        
        obj.status = new_status

    # если пришла новая сумма — обновляем
    if payload.total_amount is not None:
        obj.total_amount = payload.total_amount

    if payload.payment_status is not None:
        obj.payment_status = payload.payment_status
    if payload.paid_amount is not None:
        obj.paid_amount = payload.paid_amount
    if payload.parts_cost is not None:
        obj.parts_cost = payload.parts_cost
    if payload.paid_at is not None:
        obj.paid_at = payload.paid_at
    if payload.source is not None:
        obj.source = payload.source
    if payload.what_was_done is not None:
        obj.what_was_done = payload.what_was_done
    if payload.main_category is not None:
        obj.main_category = payload.main_category
    
    if payload.subtype is not None:
        obj.subtype = payload.subtype
    
    if payload.service_title is not None:
        obj.service_title = payload.service_title    

    await db.commit()
    await db.refresh(obj)
    return obj