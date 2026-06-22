# app/api/public.py
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.session import get_session
from app.db.models import ServiceRequest, Master

router = APIRouter(prefix="/api/public", tags=["public"])


class PublicRequestOut(BaseModel):
    id: int
    master_seq: Optional[int] = None
    status: str
    client_name: Optional[str]
    device: str
    problem_description: str
    what_was_done: Optional[str]

    total_amount: Optional[float]

    created_at: str
    date_iso: Optional[str]
    time_slot: Optional[str]

    master_id: Optional[int]
    assigned_master_id: Optional[int]
    master_name: Optional[str]

    # сервисный центр
    service_name: Optional[str] = None
    service_address: Optional[str] = None
    service_phone: Optional[str] = None

    # гарантия
    warranty_period: Optional[int] = None
    done_at: Optional[str] = None


@router.get("/requests/{request_id}", response_model=PublicRequestOut)
async def get_public_request(
    request_id: int,
    db: AsyncSession = Depends(get_session),
):
    result = await db.execute(
        select(ServiceRequest)
        .where(ServiceRequest.id == request_id)
        .options(
            # грузим мастера + его сервисный центр
            selectinload(ServiceRequest.master).selectinload(Master.service_center),
            selectinload(ServiceRequest.assigned_master).selectinload(Master.service_center),
        )
    )
    req: ServiceRequest | None = result.scalar_one_or_none()
    if not req:
        raise HTTPException(404, "Заявка не найдена")

    # определяем мастера (назначенный > владелец)
    master: Master | None = req.assigned_master or req.master
    master_name: Optional[str] = None
    service_name: Optional[str] = None
    service_address: Optional[str] = None
    service_phone: Optional[str] = None

    if master:
        parts: list[str] = []
        if getattr(master, "lastname", None):
            parts.append(master.lastname)
        if getattr(master, "name", None):
            parts.append(master.name)
        if parts:
            master_name = " ".join(parts).strip()
        else:
            master_name = master.master_id

        sc = getattr(master, "service_center", None)
        if sc:
            service_name = getattr(sc, "service_name", None)
            service_address = getattr(sc, "address", None)
            service_phone = getattr(sc, "phone", None)

    # устройство: subtype, если есть, иначе main_category
    device = req.subtype if req.subtype else req.main_category

    return PublicRequestOut(
        id=req.id,
        master_seq=req.master_seq,
        status=req.status,
        client_name=req.client_name,
        device=device,
        problem_description=req.problem_description,
        what_was_done=req.what_was_done,
        total_amount=req.total_amount,
        created_at=req.created_at.isoformat(),
        date_iso=req.date_iso.isoformat() if req.date_iso else None,
        time_slot=req.time_slot,
        master_id=req.master_id,
        assigned_master_id=req.assigned_master_id,
        master_name=master_name,
        service_name=service_name,
        service_address=service_address,
        service_phone=service_phone,
        warranty_period=req.warranty_period,
        done_at=req.done_at.isoformat() if req.done_at else None,
    )