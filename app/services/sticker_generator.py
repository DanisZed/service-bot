import os
from io import BytesIO
from datetime import datetime
from typing import Optional
import qrcode
import base64

from weasyprint import HTML, CSS
from jinja2 import Template
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.db.session import AsyncSessionLocal
from app.db.models import ServiceRequest, Master


async def generate_sticker_pdf(request_id: int, base_qr_url: str) -> BytesIO:
    """
    Генерирует PDF-файл наклейки (50x80 мм) для печати на Niimbot B1 Pro.
    Возвращает BytesIO с PDF-данными.
    """
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
        master_full_name = f"{owner.lastname or ''} {owner.name or ''}".strip()
        created_at_str = req.created_at.strftime("%d.%m.%Y %H:%M")
        # Генерируем QR-код в виде base64
        qr_data_url = generate_qr_data_url(f"{base_qr_url}/requests/{request_id}?master_id={owner.id}")

        # Загружаем HTML-шаблон
        template_path = os.path.join(os.path.dirname(__file__), "../templates/sticker_template.html")
        with open(template_path, "r", encoding="utf-8") as f:
            template_str = f.read()
        template = Template(template_str)
        html_content = template.render(
            service_name=service_name,
            master_name=master_full_name,
            request_id=request_id,
            created_at=created_at_str,
            client_name=req.client_name or "",
            client_phone=req.client_phone or "",
            address=req.address or "",
            qr_url=qr_data_url,
            master_full_name=master_full_name,
        )

        # Генерируем PDF
        pdf_file = BytesIO()
        HTML(string=html_content, base_url=os.path.dirname(template_path)).write_pdf(
            target=pdf_file,
            stylesheets=[CSS(string='@page { size: 50mm 80mm; margin: 2mm; }')]
        )
        pdf_file.seek(0)
        return pdf_file


def generate_qr_data_url(url: str) -> str:
    """Генерирует QR-код и возвращает Data URL для вставки в HTML."""
    qr = qrcode.QRCode(box_size=8, border=2)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
    buffered = BytesIO()
    img.save(buffered, format="PNG")
    img_base64 = base64.b64encode(buffered.getvalue()).decode()
    return f"data:image/png;base64,{img_base64}"