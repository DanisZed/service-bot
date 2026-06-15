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
    Генерирует PNG для печати на Niimbot B1 Pro (50x80 мм, 300 DPI).
    Размер: 600x960 пикселей.
    Цвет: чёрно-белый (1 бит/пиксель).
    """
    width, height = 600, 960
    bg_color = (255, 255, 255)
    text_color = (0, 0, 0)

    img = Image.new("RGB", (width, height), bg_color)
    draw = ImageDraw.Draw(img)

    # Подбираем шрифты под размер этикетки (можно заменить пути на свои)
    try:
        font_title = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 42)
        font_big = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 36)
        font_normal = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 28)
        font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 22)
    except:
        font_title = font_big = font_normal = font_small = ImageFont.load_default()

    y = 30

    # 1. Название сервиса или ФИО мастера
    if service_name:
        title = service_name
    else:
        title = f"{master_lastname} {master_name or ''}".strip()
    draw.text((30, y), title, fill=text_color, font=font_title)
    y += 60

    # 2. Номер заявки
    draw.text((30, y), f"ЗАЯВКА №{request_id}", fill=text_color, font=font_big)
    y += 50

    # 3. Дата
    date_str = created_at.strftime("%d.%m.%Y %H:%M")
    draw.text((30, y), f"Дата: {date_str}", fill=text_color, font=font_normal)
    y += 45

    # 4. Клиент
    if client_name:
        draw.text((30, y), f"Клиент: {client_name}", fill=text_color, font=font_normal)
        y += 40
    if client_phone:
        draw.text((30, y), f"Тел.: {client_phone}", fill=text_color, font=font_small)
        y += 35

    # 5. Адрес
    if address and address != "Мастерская":
        addr_short = address[:60] + "..." if len(address) > 60 else address
        draw.text((30, y), addr_short, fill=text_color, font=font_small)
        y += 40

    # 6. QR-код
    qr_size = 240
    qr = qrcode.QRCode(box_size=8, border=2)
    qr.add_data(qr_url)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
    qr_img = qr_img.resize((qr_size, qr_size), Image.Resampling.LANCZOS)

    qr_x = width - qr_size - 30
    qr_y = height - qr_size - 80
    img.paste(qr_img, (qr_x, qr_y))

    draw.text((qr_x, qr_y + qr_size + 10), "Сканируйте QR-код", fill=text_color, font=font_small)

    # 7. Сайт
    draw.text((30, height - 40), "www.master-rbt-crm.ru", fill=text_color, font=font_small)

    # Конвертируем в чёрно-белое (1 бит/пиксель) для чёткой печати
    img = img.convert("1")

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