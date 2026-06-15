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
    client_name: Optional[str] = None,
    client_phone: Optional[str] = None,
    address: Optional[str] = None,
) -> bytes:
    """
    Генерирует PNG для терморинтера (400x640 px ~ 50x80 мм при 200 DPI).
    """
    width, height = 400, 640
    bg_color = (255, 255, 255)   # белый фон
    text_color = (0, 0, 0)       # чёрный текст

    img = Image.new("RGB", (width, height), bg_color)
    draw = ImageDraw.Draw(img)

    # Пути к шрифтам (проверьте существование файлов, при необходимости замените)
    try:
        font_title = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 24)
        font_big = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 20)
        font_normal = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 16)
        font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 12)
    except:
        font_title = font_big = font_normal = font_small = ImageFont.load_default()

    y = 15

    # 1. Название сервиса или ФИО мастера
    if service_name:
        title = service_name
    else:
        title = f"{master_lastname} {master_name or ''}".strip()
    draw.text((15, y), title, fill=text_color, font=font_title)
    y += 35

    # 2. Номер заявки (крупно)
    draw.text((15, y), f"ЗАЯВКА №{request_id}", fill=text_color, font=font_big)
    y += 30

    # 3. Дата и время
    date_str = created_at.strftime("%d.%m.%Y %H:%M")
    draw.text((15, y), f"Дата: {date_str}", fill=text_color, font=font_normal)
    y += 25

    # 4. Клиент (если указан)
    if client_name:
        draw.text((15, y), f"Клиент: {client_name}", fill=text_color, font=font_normal)
        y += 22
    if client_phone:
        draw.text((15, y), f"Тел.: {client_phone}", fill=text_color, font=font_small)
        y += 22

    # 5. Адрес (если указан и не "Мастерская")
    if address and address != "Мастерская":
        # Обрезаем длинные адреса до 50 символов
        addr_short = address[:50] + "..." if len(address) > 50 else address
        draw.text((15, y), addr_short, fill=text_color, font=font_small)
        y += 22

    # 6. QR-код (в правом нижнем углу, размер 130x130)
    qr_size = 130
    qr = qrcode.QRCode(box_size=4, border=2)
    qr.add_data(qr_url)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
    qr_img = qr_img.resize((qr_size, qr_size))
    qr_x = width - qr_size - 15
    qr_y = height - qr_size - 35
    img.paste(qr_img, (qr_x, qr_y))

    # Подпись под QR
    draw.text((qr_x, qr_y + qr_size + 5), "QR-код", fill=text_color, font=font_small)

    # 7. Если есть свободное место, можно добавить мелкий служебный текст
    draw.text((15, height - 20), "www.master-rbt-crm.ru", fill=text_color, font=font_small)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


async def generate_sticker_for_request(request_id: int, base_qr_url: str) -> bytes:
    """Загружает данные заявки и генерирует наклейку."""
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
            client_name=req.client_name,
            client_phone=req.client_phone,
            address=req.address,
        )