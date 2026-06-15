import io
import qrcode
from PIL import Image, ImageDraw, ImageFont
from typing import Optional
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.db.session import AsyncSessionLocal
from app.db.models import ServiceRequest, Master


async def generate_sticker(
    request_id: int,
    service_name: Optional[str],
    master_lastname: str,
    master_name: Optional[str],
    created_at: datetime,
    qr_url: str,
) -> bytes:
    """
    Генерирует PNG для терморинтера (400x640 px, ~50x80 мм при 200 DPI)
    """
    width, height = 400, 640
    bg_color = (255, 255, 255)
    text_color = (0, 0, 0)

    img = Image.new("RGB", (width, height), bg_color)
    draw = ImageDraw.Draw(img)

    # Шрифты (укажите правильные пути к шрифтам на вашем сервере)
    try:
        font_title = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 24)
        font_normal = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 18)
        font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 14)
    except:
        font_title = font_normal = font_small = ImageFont.load_default()

    y = 20

    # Верхняя часть: название сервиса или ФИО мастера
    if service_name:
        title = service_name
    else:
        title = f"{master_lastname} {master_name or ''}".strip()
    draw.text((20, y), title, fill=text_color, font=font_title)
    y += 45

    # Мастер (если сервис уже показали, то просто имя)
    master_full = f"{master_lastname} {master_name or ''}".strip()
    draw.text((20, y), f"Мастер: {master_full}", fill=text_color, font=font_normal)
    y += 30

    # Дата
    date_str = created_at.strftime("%d.%m.%Y %H:%M")
    draw.text((20, y), f"Дата: {date_str}", fill=text_color, font=font_normal)
    y += 30

    # Номер заявки
    draw.text((20, y), f"Заявка №{request_id}", fill=text_color, font=font_normal)
    y += 45

    # QR-код
    qr = qrcode.QRCode(box_size=4, border=2)
    qr.add_data(qr_url)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white")
    qr_img = qr_img.resize((150, 150))
    img.paste(qr_img, (width - 170, y))

    draw.text((20, y + 60), "Сканируйте QR для", fill=text_color, font=font_small)
    draw.text((20, y + 80), "просмотра заявки", fill=text_color, font=font_small)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


async def generate_sticker_for_request(request_id: int, base_qr_url: str) -> bytes:
    """Загружает данные заявки из БД и генерирует наклейку."""
    async with AsyncSessionLocal() as session:
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
        owner = req.master
        if not owner:
            raise ValueError("Мастер-владелец не найден")

        service_name = owner.service_center.service_name if owner.service_center else None
        qr_url = f"{base_qr_url}/requests/{request_id}?master_id={owner.id}&service_center_id={owner.service_center_id or ''}"

        return await generate_sticker(
            request_id=req.id,
            service_name=service_name,
            master_lastname=owner.lastname or "",
            master_name=owner.name or "",
            created_at=req.created_at,
            qr_url=qr_url,
        )