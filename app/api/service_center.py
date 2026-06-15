from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.db.models import Master
from app.api.deps import get_current_master

router = APIRouter(prefix="/api/service-center", tags=["service-center"])

class ServiceCenterUpdate(BaseModel):
    address: Optional[str] = None
    website: Optional[str] = None
    phone: Optional[str] = None

class ServiceCenterOut(BaseModel):
    id: int
    service_id: str
    service_name: str
    address: Optional[str] = None
    website: Optional[str] = None
    phone: Optional[str] = None

@router.get("/me", response_model=ServiceCenterOut)
async def get_my_service_center(
    db: AsyncSession = Depends(get_session),
    current_master: Master = Depends(get_current_master),
):
    if current_master.is_admin != 1:
        raise HTTPException(403, "Только администратор может просматривать данные сервис-центра")
    if not current_master.service_center:
        raise HTTPException(404, "Сервис-центр не найден")
    sc = current_master.service_center
    return ServiceCenterOut(
        id=sc.id,
        service_id=sc.service_id,
        service_name=sc.service_name,
        address=sc.address,
        website=sc.website,
        phone=sc.phone,
    )

@router.patch("/me", response_model=ServiceCenterOut)
async def update_my_service_center(
    payload: ServiceCenterUpdate,
    db: AsyncSession = Depends(get_session),
    current_master: Master = Depends(get_current_master),
):
    if current_master.is_admin != 1:
        raise HTTPException(403, "Только администратор может редактировать данные сервис-центра")
    if not current_master.service_center:
        raise HTTPException(404, "Сервис-центр не найден")
    sc = current_master.service_center
    if payload.address is not None:
        sc.address = payload.address
    if payload.website is not None:
        sc.website = payload.website
    if payload.phone is not None:
        sc.phone = payload.phone
    await db.commit()
    await db.refresh(sc)
    return ServiceCenterOut(
        id=sc.id,
        service_id=sc.service_id,
        service_name=sc.service_name,
        address=sc.address,
        website=sc.website,
        phone=sc.phone,
    )