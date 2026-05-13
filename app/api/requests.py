from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal
from app.db.models import ServiceRequest
from app.api.deps import get_current_master, get_db  # см. ниже deps.py

router = APIRouter(prefix="/api/requests", tags=["requests"])


class ServiceRequestOut(BaseModel):
    id: int
    created_at: Optional[datetime] = None
    status: Optional[str] = None

    client_name: Optional[str] = None
    client_phone: Optional[str] = None

    service_title: Optional[str] = None
    main_category: Optional[str] = None
    subtype: Optional[str] = None

    address: Optional[str] = None
    address_details: Optional[str] = None
    problem_description: Optional[str] = None

    date_iso: Optional[str] = None
    time_slot: Optional[str] = None

    master_id: Optional[int] = None

    class Config:
        from_attributes = True  # Pydantic v2, если у тебя v1 — ORM mode

class ServiceRequestUpdate(BaseModel):
    status: Optional[str] = None
    master_id: Optional[int] = None


@router.get("", response_model=List[ServiceRequestOut])
async def list_requests(
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_master = Depends(get_current_master),
):
    """
    Список заявок. Пока без пагинации.
    Если передан ?status=..., фильтруем по нему.
    """
    stmt = select(ServiceRequest).order_by(ServiceRequest.id.desc())
    if status:
        stmt = stmt.where(ServiceRequest.status == status)

    result = await db.execute(stmt)
    rows = result.scalars().all()
    return rows


@router.get("/{request_id}", response_model=ServiceRequestOut)
async def get_request(
    request_id: int,
    db: AsyncSession = Depends(get_db),
    current_master = Depends(get_current_master),
):
    req = await db.get(ServiceRequest, request_id)
    if not req:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return req


@router.patch("/{request_id}", response_model=ServiceRequestOut)
async def update_request(
    request_id: int,
    payload: ServiceRequestUpdate,
    db: AsyncSession = Depends(get_db),
    current_master = Depends(get_current_master),
):
    req = await db.get(ServiceRequest, request_id)
    if not req:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

    if payload.status is not None:
        req.status = payload.status
    if payload.master_id is not None:
        req.master_id = payload.master_id

    await db.commit()
    await db.refresh(req)
    return req