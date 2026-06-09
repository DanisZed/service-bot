# app/api/requests.py
from datetime import datetime, date
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ServiceRequest, Master
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
    assigned_master_id: Optional[int] = None

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
    assigned_master_id: Optional[int] = None  

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
    stmt = (
        select(ServiceRequest)
        .where(
            (ServiceRequest.master_id == current_master.id) |
            (ServiceRequest.assigned_master_id == current_master.id)
        )
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
    if not req or (req.master_id != current_master.id and req.assigned_master_id != current_master.id):
        raise HTTPException(status_code=404, detail="Not found")
    return req


@router.patch("/{request_id}", response_model=ServiceRequestOut)
async def update_service_request(
    request_id: int,
    payload: ServiceRequestUpdate,
    db: AsyncSession = Depends(get_db),
    current_master=Depends(get_current_master),
):
    # Находим заявку
    obj = await db.get(ServiceRequest, request_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Request not found")

    # Проверяем права: владелец ИЛИ назначенный мастер
    is_owner = (obj.master_id == current_master.id)
    is_assigned = (obj.assigned_master_id == current_master.id)
    if not (is_owner or is_assigned):
        raise HTTPException(status_code=403, detail="Нет прав на редактирование")

    # --- Обработка статуса (с простановкой дат) ---
    if payload.status is not None and payload.status != obj.status:
        now = datetime.utcnow()
        if payload.status == "in_work" and obj.status != "in_work":
            obj.in_work_at = now
        if payload.status == "done" and obj.status != "done":
            obj.done_at = now
            if not obj.in_work_at:
                obj.in_work_at = now
        if payload.status == "canceled" and obj.status != "canceled":
            obj.cancelled_at = now
            obj.total_amount = 0
        obj.status = payload.status

    # --- Смена исполнителя (только если передан assigned_master_id) ---
    if payload.assigned_master_id is not None:
        if payload.assigned_master_id == current_master.id:
            raise HTTPException(400, "Нельзя назначить заявку самому себе")
        target_master = await db.get(Master, payload.assigned_master_id)
        if not target_master:
            raise HTTPException(404, "Мастер не найден")
        obj.assigned_master_id = payload.assigned_master_id
        # Если заявка была новой – переводим в статус "assigned"
        if obj.status == "new" and payload.status is None:
            obj.status = "assigned"
        # Отправляем уведомление новому мастеру
        from app.services.master_notify import notify_master_request_created
        await notify_master_request_created(obj.id)

    # --- Обновление остальных полей (доступно и владельцу, и исполнителю) ---
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