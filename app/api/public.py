# app/api/public.py
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_session
from app.db.models import ServiceRequest

router = APIRouter(prefix="/api/public", tags=["public"])

class PublicRequestOut(BaseModel):
    id: int
    status: str
    client_name: Optional[str]
    master_id: Optional[int] = None
    assigned_master_id: Optional[int] = None
    device: str          # можно склеить main_category + subtype
    problem_description: str
    what_was_done: Optional[str]
    total_amount: Optional[float]
    created_at: str
    # добавляйте только то, что можно показывать клиенту
    date_iso: Optional[str]
    time_slot: Optional[str]

@router.get("/requests/{request_id}", response_model=PublicRequestOut)
async def get_public_request(
    request_id: int,
    db: AsyncSession = Depends(get_session),
):
    result = await db.execute(select(ServiceRequest).where(ServiceRequest.id == request_id))
    req = result.scalar_one_or_none()
    if not req:
        raise HTTPException(404, "Заявка не найдена")
    # Формируем название устройства
    device = f"{req.main_category} / {req.subtype}" if req.subtype else req.main_category
    return PublicRequestOut(
        id=req.id,
        status=req.status,
        client_name=req.client_name,
        master_id=req.master_id,
        assigned_master_id=req.assigned_master_id,
        device=device,
        problem_description=req.problem_description,
        what_was_done=req.what_was_done,
        total_amount=req.total_amount,
        created_at=req.created_at.isoformat(),
        date_iso=req.date_iso.isoformat() if req.date_iso else None,
        time_slot=req.time_slot,
    )