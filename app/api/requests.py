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
from app.services.notifications import schedule_visit_reminders



router = APIRouter(prefix="/api/requests", tags=["requests"])



class ServiceRequestOut(BaseModel):
    id: int



    # Время создания и статус заявки
    created_at: datetime
    status: str



    # Владелец и исполнитель
    master_id: Optional[int] = None
    master_seq: int | None = None
    assigned_master_id: Optional[int] = None
    assigned_master_name: Optional[str] = None



    # Сервисный центр и диспетчерская передача
    service_center_id: Optional[int] = None
    is_from_dispatcher: bool = False
    dispatcher_commission_percent: Optional[float] = None
    dispatcher_fee_amount: Optional[float] = None



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
    parts_cost: Optional[float] = None
    currency: str
    payment_status: str
    paid_amount: Optional[float] = None
    paid_at: Optional[datetime] = None



    # Источник и внешние ссылки
    source: str
    lead_source_id: Optional[int] = None
    lead_source_name: Optional[str] = None
    yandex_url: Optional[str] = None
    google_url: Optional[str] = None



    # Даты статусов
    done_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    in_work_at: Optional[datetime] = None



    class Config:
        from_attributes = True



class ServiceRequestUpdate(BaseModel):
    status: Optional[str] = None
    master_id: Optional[int] = None
    assigned_master_id: Optional[int] = None



    total_amount: Optional[float] = None
    parts_cost: Optional[float] = None
    payment_status: Optional[str] = None
    paid_amount: Optional[float] = None
    paid_at: Optional[datetime] = None



    source: Optional[str] = None



    what_was_done: Optional[str] = None
    repair_description: Optional[str] = None
    warranty_period: Optional[int] = None



    main_category: Optional[str] = None
    subtype: Optional[str] = None
    service_title: Optional[str] = None



    address: Optional[str] = None
    address_details: Optional[str] = None



    date_iso: Optional[date] = None
    time_slot: Optional[str] = None



class CreateRequestFromWeb(BaseModel):
    problem_description: str
    location_type: str
    master_id: Optional[int] = None
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
    lead_source_id: Optional[int] = None
    yandex_url: Optional[str] = None



class WallboardRequestItem(BaseModel):
    id: int
    master_seq: int
    status: str
    created_at: datetime



    client_name: Optional[str] = None
    client_phone: Optional[str] = None
    problem_description: Optional[str] = None
    subtype: Optional[str] = None



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



def has_request_access(
    request: ServiceRequest,
    current_master: Master,
) -> bool:
    """
    Диспетчер сервис-центра видит все заявки своего центра.
    Мастер видит свои заявки и заявки, назначенные ему.
    """
    has_center_access = (
        current_master.is_admin == 1
        and current_master.service_center_id is not None
        and request.service_center_id == current_master.service_center_id
    )


    has_master_access = (
        request.master_id == current_master.id
        or request.assigned_master_id == current_master.id
    )


    return has_center_access or has_master_access



@router.get("/wallboard", response_model=WallboardResponse)
async def wallboard_requests(
    db: AsyncSession = Depends(get_db),
    current_master: Master = Depends(get_current_master),
):
    """
    Данные для инфотабло:
    - новые заявки текущего мастера в мастерской
    - заявки в работе в мастерской
    """
    NEW_STATUSES = ("new", "assigned")
    WORK_STATUS = "in_work"
    WORKSHOP_LOCATION = "workshop"
    WORKSHOP_ADDRESS = "Мастерская"



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
    stmt = select(ServiceRequest)



    if current_master.is_admin == 1 and current_master.service_center_id:
        # Диспетчер сервис-центра видит все заявки центра.
        stmt = stmt.where(
            ServiceRequest.service_center_id == current_master.service_center_id
        )
    else:
        # Мастер видит свои заявки и заявки, назначенные ему.
        stmt = stmt.where(
            (ServiceRequest.master_id == current_master.id)
            | (ServiceRequest.assigned_master_id == current_master.id)
        )



    if status:
        stmt = stmt.where(ServiceRequest.status == status)



    stmt = stmt.order_by(ServiceRequest.id.desc())


    result = await db.execute(stmt)
    rows = result.scalars().all()
    return rows



@router.get("/slots")
async def get_available_slots(
    date: str,
    master_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    current_master: Master = Depends(get_current_master),
):
    """
    Возвращает временные слоты мастера на дату.
    Диспетчер может проверить занятость любого мастера своего центра.
    """
    try:
        target_date = datetime.strptime(date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Некорректная дата. Используйте формат YYYY-MM-DD.",
        )



    target_master_id = current_master.id



    if master_id is not None:
        if current_master.is_admin != 1:
            raise HTTPException(
                status_code=403,
                detail="Только диспетчер может проверять слоты другого мастера",
            )



        target_master = await db.get(Master, master_id)



        if not target_master:
            raise HTTPException(status_code=404, detail="Мастер не найден")



        if (
            not current_master.service_center_id
            or target_master.service_center_id
            != current_master.service_center_id
        ):
            raise HTTPException(
                status_code=403,
                detail="Мастер не принадлежит вашему сервисному центру",
            )



        target_master_id = target_master.id



    time_slots = [
        ("09:00", "10:00"),
        ("10:00", "11:00"),
        ("11:00", "12:00"),
        ("12:00", "13:00"),
        ("13:00", "14:00"),
        ("14:00", "15:00"),
        ("15:00", "16:00"),
        ("16:00", "17:00"),
        ("17:00", "18:00"),
    ]



    result = await db.execute(
        select(ServiceRequest.time_slot).where(
            ServiceRequest.assigned_master_id == target_master_id,
            ServiceRequest.date_iso == target_date,
            ServiceRequest.status.in_(
                ["new", "assigned", "in_work", "confirmed"]
            ),
        )
    )



    booked_slots = {
        row[0]
        for row in result
        if row[0]
    }



    slots = [
        {
            "time_slot": f"{start}-{end}",
            "is_booked": f"{start}-{end}" in booked_slots,
        }
        for start, end in time_slots
    ]



    return {
        "date": date,
        "master_id": target_master_id,
        "slots": slots,
    }



@router.get("/{request_id}", response_model=ServiceRequestOut)
async def get_request(
    request_id: int,
    db: AsyncSession = Depends(get_db),
    current_master=Depends(get_current_master),
):
    req = await db.get(ServiceRequest, request_id)



    if not req or not has_request_access(req, current_master):
        raise HTTPException(status_code=404, detail="Not found")



    return req



@router.post("/create", response_model=ServiceRequestOut, status_code=status.HTTP_201_CREATED)
async def create_request_from_web(
    payload: CreateRequestFromWeb,
    db: AsyncSession = Depends(get_db),
    current_master: Master = Depends(get_current_master),
):
    """
    Создаёт заявку из веб-интерфейса.
    Если master_id не указан, заявка назначается текущему мастеру.
    """
    assigned_master_id = payload.master_id or current_master.id
    owner_master_id = current_master.id
    service_center_id = current_master.service_center_id



    data = {
        "user_id": current_master.max_user_id,
        "chat_id": current_master.max_user_id,
        "master_id": owner_master_id,
        "assigned_master_id": assigned_master_id,
        "service_center_id": service_center_id,
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
        "lead_source_id": payload.lead_source_id,
        "yandex_url": payload.yandex_url,
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
    obj = await db.get(ServiceRequest, request_id)



    if not obj or not has_request_access(obj, current_master):
        raise HTTPException(status_code=404, detail="Request not found")



    provided_fields = payload.model_fields_set



    # --- Статус ---
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
            obj.dispatcher_fee_amount = 0



        obj.status = payload.status



    # --- Назначение исполнителя ---
    if "assigned_master_id" in provided_fields:
        if payload.assigned_master_id is None:
            obj.assigned_master_id = None
            obj.is_from_dispatcher = False
            obj.dispatcher_commission_percent = None
            obj.dispatcher_fee_amount = None
        else:
            if payload.assigned_master_id == obj.master_id:
                raise HTTPException(
                    status_code=400,
                    detail="Нельзя назначить заявку владельцу заявки",
                )



            target_master = await db.get(
                Master, payload.assigned_master_id
            )



            if not target_master:
                raise HTTPException(status_code=404, detail="Мастер не найден")



            if (
                current_master.is_admin != 1
                or not current_master.service_center_id
                or target_master.service_center_id
                != current_master.service_center_id
            ):
                raise HTTPException(
                    status_code=403,
                    detail="Мастер не принадлежит вашему сервисному центру",
                )



            obj.assigned_master_id = payload.assigned_master_id
            obj.is_from_dispatcher = obj.master_id != obj.assigned_master_id



            if obj.is_from_dispatcher:
                obj.dispatcher_commission_percent = (
                    target_master.dispatcher_commission_percent
                )
            else:
                obj.dispatcher_commission_percent = None
                obj.dispatcher_fee_amount = None



            if obj.status == "new":
                obj.status = "assigned"



            await notify_master_request_created(obj.id)



    # --- Дата и время визита ---
    if "date_iso" in provided_fields or "time_slot" in provided_fields:
        new_date = (
            payload.date_iso
            if payload.date_iso is not None
            else obj.date_iso
        )



        new_time_slot = (
            payload.time_slot
            if payload.time_slot is not None
            else obj.time_slot
        )



        if new_date and new_time_slot:
            conflict_stmt = select(ServiceRequest).where(
                ServiceRequest.assigned_master_id == obj.assigned_master_id,
                ServiceRequest.date_iso == new_date,
                ServiceRequest.time_slot == new_time_slot,
                ServiceRequest.id != obj.id,
                ServiceRequest.status.in_(
                    ["new", "assigned", "in_work", "confirmed"]
                ),
            )



            conflict_result = await db.execute(conflict_stmt)
            conflict = conflict_result.scalar_one_or_none()



            if conflict:
                raise HTTPException(
                    status_code=409,
                    detail="Выбранное время уже занято для этого исполнителя",
                )



            try:
                start_time, end_time = new_time_slot.split("-")
                start_hour, start_minute = map(int, start_time.split(":"))
                end_hour, end_minute = map(int, end_time.split(":"))



                obj.datetime_from = datetime.combine(
                    new_date,
                    datetime.min.time(),
                ).replace(
                    hour=start_hour,
                    minute=start_minute,
                )



                obj.datetime_to = datetime.combine(
                    new_date,
                    datetime.min.time(),
                ).replace(
                    hour=end_hour,
                    minute=end_minute,
                )
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail="Некорректный временной слот",
                )



        obj.date_iso = new_date
        obj.time_slot = new_time_slot



    # --- Адрес ---
    if "address" in provided_fields:
        obj.address = payload.address



    if "address_details" in provided_fields:
        obj.address_details = payload.address_details



    # --- Финансы ---
    if payload.total_amount is not None:
        obj.total_amount = payload.total_amount



    if payload.parts_cost is not None:
        obj.parts_cost = payload.parts_cost



    if payload.payment_status is not None:
        obj.payment_status = payload.payment_status



    if payload.paid_amount is not None:
        obj.paid_amount = payload.paid_amount



    if payload.paid_at is not None:
        obj.paid_at = payload.paid_at



    # Пересчитываем вознаграждение диспетчера.
    if obj.is_from_dispatcher and obj.total_amount is not None:
        if obj.dispatcher_commission_percent is not None:
            obj.dispatcher_fee_amount = (
                obj.total_amount
                * obj.dispatcher_commission_percent
                / 100
            )
        else:
            obj.dispatcher_fee_amount = None



    # --- Прочие поля ---
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



    if not req or not has_request_access(req, current_master):
        raise HTTPException(404, "Заявка не найдена или нет доступа")



    frontend_base = os.getenv(
        "PANEL_BASE_URL",
        "https://panel.master-rbt-crm.ru",
    )
    img_bytes = await generate_sticker_for_request(request_id, frontend_base)



    return Response(content=img_bytes, media_type="image/png")