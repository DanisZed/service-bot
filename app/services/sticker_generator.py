import io
import qrcode
from PIL import Image, ImageDraw, ImageFont
from typing import Optional
from datetime import datetime
# Добавляем импорт для жадной загрузки
from sqlalchemy.orm import selectinload

async def generate_sticker_for_request(request_id: int, base_qr_url: str) -> bytes:
    """Загружает данные заявки из БД и генерирует наклейку."""
    from app.db.session import AsyncSessionLocal
    from app.db.models import ServiceRequest, Master
    from sqlalchemy import select

    async with AsyncSessionLocal() as session:
        # Исправленный запрос: явно подгружаем владельца и его сервис-центр
        stmt = (
            select(ServiceRequest)
            .where(ServiceRequest.id == request_id)
            .options(
                selectinload(ServiceRequest.master).selectinload(Master.service_center)
            )
        )
        result = await session.execute(stmt)
        req = result.scalar_one_or_none()
        
        if not req:
            raise ValueError("Заявка не найдена")
        
        # После такой загрузки req.master и req.master.service_center уже будут доступны
        owner = req.master
        if not owner:
            raise ValueError("Мастер-владелец не найден")
        
        # Безопасно получаем название сервиса
        service_name = owner.service_center.service_name if owner.service_center else None
        
        qr_url = f"{base_qr_url}/requests/{request_id}?master_id={owner.id}&service_center_id={owner.service_center_id or ''}"
        
        # Генерируем наклейку
        return await generate_sticker(
            request_id=req.id,
            service_name=service_name,
            master_lastname=owner.lastname or "",
            master_name=owner.name or "",
            created_at=req.created_at,
            qr_url=qr_url,
        )