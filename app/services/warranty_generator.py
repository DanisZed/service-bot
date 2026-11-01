import io
import os
from datetime import timedelta
from pathlib import Path


import qrcode
from reportlab.lib.pagesizes import A5
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase.pdfmetrics import registerFontFamily
from reportlab.pdfgen import canvas


from app.db.models import ResaleDeal




FONT_DIR = Path(__file__).resolve().parent.parent / "assets" / "fonts"




pdfmetrics.registerFont(
    TTFont(
        "DejaVu",
        str(FONT_DIR / "DejaVuSans.ttf"),
    )
)


pdfmetrics.registerFont(
    TTFont(
        "DejaVu-Bold",
        str(FONT_DIR / "DejaVuSans-Bold.ttf"),
    )
)


registerFontFamily(
    "DejaVu",
    normal="DejaVu",
    bold="DejaVu-Bold",
    italic="DejaVu",
    boldItalic="DejaVu-Bold",
)






def _get_seller(deal: ResaleDeal):
    master = deal.master
    service_center = master.service_center if master else None


    if service_center:
        return {
            "type": "service_center",
            "name": service_center.service_name,
            "phone": service_center.phone,
            "address": service_center.address,
        }


    seller_name = None
    if master:
        seller_name = " ".join(
            part
            for part in [master.lastname, master.name]
            if part
        ).strip() or None


    return {
        "type": "master",
        "name": seller_name,
        "phone": master.phone if master else None,
        "address": None,
    }




def _get_warranty_until(deal: ResaleDeal):
    if not deal.sold_at or not deal.warranty_months:
        return None


    return deal.sold_at + timedelta(days=deal.warranty_months * 30)




def _make_qr_image(url: str):
    qr = qrcode.QRCode(box_size=6, border=2)
    qr.add_data(url)
    qr.make(fit=True)


    image = qr.make_image(fill_color="black", back_color="white")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer






def build_warranty_pdf(deal: ResaleDeal) -> bytes:
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A5)


    width, height = A5
    x = 12 * mm
    y = height - 15 * mm


    device = deal.resale_item.name if deal.resale_item else deal.title
    seller = _get_seller(deal)
    warranty_until = _get_warranty_until(deal)


    c.setFont("DejaVu-Bold", 16)
    c.drawString(x, y, "ГАРАНТИЙНЫЙ ТАЛОН")


    y -= 12 * mm
    c.setFont("DejaVu", 11)


    lines = [
        f"Техника: {device}",
        f"Дата продажи: {deal.sold_at.strftime('%d.%m.%Y') if deal.sold_at else '—'}",
        f"Срок гарантии: {deal.warranty_months or 0} мес.",
        f"Гарантия до: {warranty_until.strftime('%d.%m.%Y') if warranty_until else '—'}",
        f"Продавец: {seller['name'] or '—'}",
    ]


    if seller["address"]:
        lines.append(f"Адрес: {seller['address']}")


    if seller["phone"]:
        lines.append(f"Телефон: {seller['phone']}")


    for line in lines:
        c.drawString(x, y, line)
        y -= 7 * mm


    client_base = os.getenv(
        "CLIENT_BASE_URL",
        "https://client.rbt-crm.ru",
    )
    qr_url = f"{client_base}/warranty/{deal.public_id}"
    qr_buffer = _make_qr_image(qr_url)


    qr_size = 34 * mm
    c.drawImage(
        ImageReader(qr_buffer),
        width - qr_size - 12 * mm,
        12 * mm,
        width=qr_size,
        height=qr_size,
    )


    c.showPage()
    c.save()
    return buffer.getvalue()






def build_warranty_sticker_pdf(deal: ResaleDeal) -> bytes:
    buffer = io.BytesIO()
    width, height = 100 * mm, 50 * mm
    c = canvas.Canvas(buffer, pagesize=(width, height))


    device = deal.resale_item.name if deal.resale_item else deal.title
    warranty_until = _get_warranty_until(deal)


    c.setFont("DejaVu-Bold", 12)
    c.drawString(8 * mm, height - 10 * mm, "ГАРАНТИЙНЫЙ ТАЛОН")


    c.setFont("DejaVu", 9)
    c.drawString(8 * mm, height - 18 * mm, device[:38])


    if deal.sold_at:
        c.drawString(
            8 * mm,
            height - 25 * mm,
            f"Продано: {deal.sold_at.strftime('%d.%m.%Y')}",
        )


    if deal.warranty_months:
        c.drawString(
            8 * mm,
            height - 32 * mm,
            f"Гарантия: {deal.warranty_months} мес.",
        )


    if warranty_until:
        c.drawString(
            8 * mm,
            height - 39 * mm,
            f"До: {warranty_until.strftime('%d.%m.%Y')}",
        )


    client_base = os.getenv(
        "CLIENT_BASE_URL",
        "https://client.rbt-crm.ru",
    )
    qr_url = f"{client_base}/warranty/{deal.public_id}"
    qr_buffer = _make_qr_image(qr_url)


    qr_size = 34 * mm
    c.drawImage(
        ImageReader(qr_buffer),
        width - qr_size - 6 * mm,
        6 * mm,
        width=qr_size,
        height=qr_size,
    )


    c.showPage()
    c.save()
    return buffer.getvalue()