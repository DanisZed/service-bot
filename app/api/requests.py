# app/api/requests.py
import os
from datetime import datetime, date
from typing import List, Optional


from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


from app.db.models import ServiceRequest, Master
from app.api.deps import get_current_master, get_db


from app.services.masters_notify import notify_master_request_created
from app.services.requests import create_service_request
from app.services.sticker_generator import generate_sticker_for_request


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
    repair_description: Optional[str] = None
    warranty_period: Optional[int] = None

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
    repair_description: Optional[str] = None
    warranty_period: Optional[int] = None

    # Техника и услуга
    main_category: Optional[str] = None
    subtype: Optional[str] = None
    service_title: Optional[str] = None


class CreateRequestFromWeb(BaseModel):
    problem_description: str
    location_type: str
    master_id: Optional[int] = None           # если не указан, назначается текущему мастеру
    client_name: Optional[str] = None
    client_phone: Optional[str] = None
    address: Optional[str] = None
    address_details: Optional[str] = None
    date_iso: Optional[str] = None
    time_slot: Optional[str] = None
    main_category: str = "general"
    subtype: str = "general"
    service_title: Optional[str] = None
    custom_device: Optional[str] = None
    repair_description: Optional[str] = None
    warranty_period: Optional[int] = None
    total_amount: Optional[float] = None
    parts_cost: Optional[float] = None
    source: str = "web"


class WallboardRequestItem(BaseModel):
    id: int
    master_seq: int                 # номер заявки для мастера
    status: str
    created_at: datetime

    # поля для табло
    client_name: Optional[str] = None
    client_phone: Optional[str] = None
    problem_description: Optional[str] = None
    subtype: Optional[str] = None

    # мастер / назначенный мастер
    master_name: Optional[str] = None
    assigned_master_name: Optional[str] = None

    class Config:
        from_attributes = True


class WallboardMeta(BaseModel):
    service_name: Optional[str] = None
    address: Optional[str] = None


class WallboardResponse(BaseModel):
    new: List[WallboardRequestItem]
    in_work: List[WallboardRequestItem]
    meta: Optional[WallboardMeta] = None


@router.get("/wallboard", response_model=WallboardResponse)
async def wallboard_requests(
    db: AsyncSession = Depends(get_db),
    current_master: Master = Depends(get_current_master),
):
    """
    Данные для инфотабло:
    - новые заявки текущего мастера (в мастерской)
    - заявки в работе в мастерской
    """
    NEW_STATUSES = ("new", "assigned")
    WORK_STATUS = "in_work"
    WORKSHOP_LOCATION = "workshop"
    WORKSHOP_ADDRESS = "Мастерская"

    # --- новые заявки в мастерской ---
    stmt_new = (
        select(ServiceRequest)
        .where(
            ServiceRequest.master_id == current_master.id,
            ServiceRequest.status.in_(NEW_STATUSES),
            ServiceRequest.location_type == WORKSHOP_LOCATION,
            ServiceRequest.address == WORKSHOP_ADDRESS,
        )
        .order_by(ServiceRequest.id.desc())
        .limit(30)
    )
    res_new = await db.execute(stmt_new)
    rows_new = res_new.scalars().all()

    new_items: List[WallboardRequestItem] = []
    for r in rows_new:
        new_items.append(
            WallboardRequestItem(
                id=r.id,
                master_seq=r.master_seq or 0,
                status=r.status,
                created_at=r.created_at,
                client_name=r.client_name,
                client_phone=r.client_phone,
                problem_description=r.problem_description,
                subtype=r.subtype,
                master_name=r.master.name if r.master else None,
                assigned_master_name=(
                    r.assigned_master.name if r.assigned_master else None
                ),
            )
        )

    # --- в работе в мастерской ---
    stmt_in = (
        select(ServiceRequest)
        .where(
            ServiceRequest.master_id == current_master.id,
            ServiceRequest.status == WORK_STATUS,
            ServiceRequest.location_type == WORKSHOP_LOCATION,
            ServiceRequest.address == WORKSHOP_ADDRESS,
        )
        .order_by(ServiceRequest.id.desc())
        .limit(30)
    )
    res_in = await db.execute(stmt_in)
    rows_in = res_in.scalars().all()

    in_items: List[WallboardRequestItem] = []
    for r in rows_in:
        in_items.append(
            WallboardRequestItem(
                id=r.id,
                master_seq=r.master_seq or 0,
                status=r.status,
                created_at=r.created_at,
                client_name=r.client_name,
                client_phone=r.client_phone,
                problem_description=r.problem_description,
                subtype=r.subtype,
                master_name=r.master.name if r.master else None,
                assigned_master_name=(
                    r.assigned_master.name if r.assigned_master else None
                ),
            )
        )

    # тут реально достаём service_name и address
    service_name = None
    service_address = None
    if current_master.service_center:
        service_name = current_master.service_center.service_name
        service_address = current_master.service_center.address

    meta = WallboardMeta(
      service_name=service_name,
      address=service_address,
    )

    return WallboardResponse(new=new_items, in_work=in_items, meta=meta)


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


@router.post("/create", response_model=ServiceRequestOut, status_code=status.HTTP_201_CREATED)
async def create_request_from_web(
    payload: CreateRequestFromWeb,
    db: AsyncSession = Depends(get_db),
    current_master: Master = Depends(get_current_master),
):
    """
    Создаёт заявку из веб-интерфейса (аналог бота).
    Авторизация по JWT-куке. Если master_id не указан, заявка назначается текущему мастеру.
    """
    # Определяем исполнителя и владельца
    assigned_master_id = payload.master_id or current_master.id
    owner_master_id = current_master.id

    data = {
        "user_id": current_master.max_user_id,
        "chat_id": current_master.max_user_id,
        "master_id": owner_master_id,
        "assigned_master_id": assigned_master_id,
        "client_name": payload.client_name,
        "client_phone": payload.client_phone,
        "main_category": payload.main_category,
        "subtype": payload.subtype,
        "custom_device": payload.custom_device,
        "service_title": payload.service_title,
        "problem_description": payload.problem_description,
        "location_type": payload.location_type,
        "address": payload.address,
        "address_details": payload.address_details,
        "date_iso": payload.date_iso,
        "time_slot": payload.time_slot,
        "datetime_from": None,
        "datetime_to": None,
        "total_amount": payload.total_amount,
        "parts_cost": payload.parts_cost,
        "currency": "RUB",
        "payment_status": "unpaid",
        "paid_amount": None,
        "paid_at": None,
        "source": payload.source,
        "yandex_url": None,
        "google_url": None,
        "meta": None,
    }

    req = await create_service_request(db, data)
    await notify_master_request_created(req.id)
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
    if payload.repair_description is not None:
        obj.repair_description = payload.repair_description
    if payload.warranty_period is not None:
        obj.warranty_period = payload.warranty_period

    await db.commit()
    await db.refresh(obj)
    return obj


@router.get("/{request_id}/sticker")
async def get_request_sticker(
    request_id: int,
    db: AsyncSession = Depends(get_db),
    current_master: Master = Depends(get_current_master),
):
    req = await db.get(ServiceRequest, request_id)
    if not req or (req.master_id != current_master.id and req.assigned_master_id != current_master.id):
        raise HTTPException(404, "Заявка не найдена или нет доступа")
    frontend_base = os.getenv("PANEL_BASE_URL", "https://panel.master-rbt-crm.ru")
    img_bytes = await generate_sticker_for_request(request_id, frontend_base)
    return Response(content=img_bytes, media_type="image/png")