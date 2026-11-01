import io
import os
from datetime import timedelta
from pathlib import Path


import qrcode
from reportlab.lib import colors
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




BRAND_COLOR = colors.HexColor("#1F4E79")
LIGHT_COLOR = colors.HexColor("#F2F6FA")
BORDER_COLOR = colors.HexColor("#C9D6E3")
TEXT_COLOR = colors.HexColor("#1F2937")
MUTED_COLOR = colors.HexColor("#6B7280")




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






def _draw_page_frame(c, width, height):
    c.setStrokeColor(BORDER_COLOR)
    c.setLineWidth(1)
    c.roundRect(
        8 * mm,
        8 * mm,
        width - 16 * mm,
        height - 16 * mm,
        4 * mm,
        stroke=1,
        fill=0,
    )




def _draw_header(c, width, height, title="ГАРАНТИЙНЫЙ ТАЛОН"):
    header_height = 18 * mm


    c.setFillColor(BRAND_COLOR)
    c.roundRect(
        8 * mm,
        height - 8 * mm - header_height,
        width - 16 * mm,
        header_height,
        4 * mm,
        stroke=0,
        fill=1,
    )


    c.setFillColor(colors.white)
    c.setFont("DejaVu-Bold", 15)
    c.drawCentredString(
        width / 2,
        height - 8 * mm - 11.5 * mm,
        title,
    )


    c.setFont("DejaVu", 8)
    c.drawCentredString(
        width / 2,
        height - 8 * mm - 15.5 * mm,
        "Документ подтверждает факт продажи и гарантийные обязательства",
    )




def _draw_info_row(c, x, y, width, label, value):
    row_height = 8 * mm


    c.setFillColor(LIGHT_COLOR)
    c.roundRect(
        x,
        y - row_height,
        width,
        row_height,
        1.5 * mm,
        stroke=0,
        fill=1,
    )


    c.setFillColor(MUTED_COLOR)
    c.setFont("DejaVu", 8.5)
    c.drawString(x + 3 * mm, y - 5.4 * mm, label)


    c.setFillColor(TEXT_COLOR)
    c.setFont("DejaVu-Bold", 9.5)
    c.drawString(x + 38 * mm, y - 5.4 * mm, value)


    return y - row_height - 2.5 * mm






def build_warranty_pdf(deal: ResaleDeal) -> bytes:
    buffer = io.BytesIO()
    width, height = A5
    c = canvas.Canvas(buffer, pagesize=A5)


    _draw_page_frame(c, width, height)
    _draw_header(c, width, height)


    device = deal.resale_item.name if deal.resale_item else deal.title
    seller = _get_seller(deal)
    warranty_until = _get_warranty_until(deal)


    x = 14 * mm
    content_width = width - 28 * mm
    y = height - 34 * mm


    c.setFillColor(TEXT_COLOR)
    c.setFont("DejaVu-Bold", 11)
    c.drawString(x, y, "Информация о товаре")


    y -= 5 * mm


    y = _draw_info_row(
        c,
        x,
        y,
        content_width,
        "Техника",
        device,
    )


    y = _draw_info_row(
        c,
        x,
        y,
        content_width,
        "Дата продажи",
        deal.sold_at.strftime("%d.%m.%Y") if deal.sold_at else "—",
    )


    y = _draw_info_row(
        c,
        x,
        y,
        content_width,
        "Срок гарантии",
        f"{deal.warranty_months or 0} мес.",
    )


    y = _draw_info_row(
        c,
        x,
        y,
        content_width,
        "Гарантия до",
        warranty_until.strftime("%d.%m.%Y") if warranty_until else "—",
    )


    y -= 4 * mm


    c.setFillColor(TEXT_COLOR)
    c.setFont("DejaVu-Bold", 11)
    c.drawString(x, y, "Продавец")


    y -= 5 * mm


    y = _draw_info_row(
        c,
        x,
        y,
        content_width,
        "Наименование",
        seller["name"] or "—",
    )


    if seller["address"]:
        y = _draw_info_row(
            c,
            x,
            y,
            content_width,
            "Адрес",
            seller["address"],
        )


    if seller["phone"]:
        y = _draw_info_row(
            c,
            x,
            y,
            content_width,
            "Телефон",
            seller["phone"],
        )


    client_base = os.getenv(
        "CLIENT_BASE_URL",
        "https://client.rbt-crm.ru",
    )
    qr_url = f"{client_base}/warranty/{deal.public_id}"
    qr_buffer = _make_qr_image(qr_url)


    qr_size = 30 * mm
    qr_x = width - qr_size - 14 * mm
    qr_y = 14 * mm


    c.drawImage(
        ImageReader(qr_buffer),
        qr_x,
        qr_y,
        width=qr_size,
        height=qr_size,
    )


    c.setFillColor(MUTED_COLOR)
    c.setFont("DejaVu", 7.5)
    c.drawString(
        x,
        qr_y + qr_size / 2 + 3 * mm,
        "Отсканируйте QR-код,",
    )
    c.drawString(
        x,
        qr_y + qr_size / 2 - 1 * mm,
        "чтобы проверить гарантию",
    )


    c.setFillColor(TEXT_COLOR)
    c.setFont("DejaVu", 8)
    c.drawString(
        x,
        13 * mm,
        "Гарантия не распространяется на механические повреждения,",
    )
    c.drawString(
        x,
        9 * mm,
        "попадание влаги, самостоятельный ремонт и нарушение правил эксплуатации.",
    )


    c.showPage()
    c.save()
    return buffer.getvalue()






def build_warranty_sticker_pdf(deal: ResaleDeal) -> bytes:
    buffer = io.BytesIO()
    width, height = 100 * mm, 50 * mm
    c = canvas.Canvas(buffer, pagesize=(width, height))


    c.setFillColor(colors.white)
    c.rect(0, 0, width, height, stroke=0, fill=1)


    c.setStrokeColor(colors.black)
    c.setLineWidth(0.8)
    c.roundRect(
        2 * mm,
        2 * mm,
        width - 4 * mm,
        height - 4 * mm,
        2 * mm,
        stroke=1,
        fill=0,
    )


    device = deal.resale_item.name if deal.resale_item else deal.title
    warranty_until = _get_warranty_until(deal)


    c.setFillColor(colors.black)
    c.setFont("DejaVu-Bold", 11)
    c.drawString(6 * mm, height - 9 * mm, "ГАРАНТИЙНЫЙ ТАЛОН")


    c.setFont("DejaVu-Bold", 9)
    c.drawString(6 * mm, height - 16 * mm, device[:38])


    c.setFont("DejaVu", 8)


    if deal.sold_at:
        c.drawString(
            6 * mm,
            height - 23 * mm,
            f"Продано: {deal.sold_at.strftime('%d.%m.%Y')}",
        )


    if deal.warranty_months:
        c.drawString(
            6 * mm,
            height - 29 * mm,
            f"Гарантия: {deal.warranty_months} мес.",
        )


    if warranty_until:
        c.drawString(
            6 * mm,
            height - 35 * mm,
            f"Действует до: {warranty_until.strftime('%d.%m.%Y')}",
        )


    client_base = os.getenv(
        "CLIENT_BASE_URL",
        "https://client.rbt-crm.ru",
    )
    qr_url = f"{client_base}/warranty/{deal.public_id}"
    qr_buffer = _make_qr_image(qr_url)


    qr_size = 32 * mm
    c.drawImage(
        ImageReader(qr_buffer),
        width - qr_size - 6 * mm,
        6 * mm,
        width=qr_size,
        height=qr_size,
    )


    c.setFont("DejaVu", 6.5)
    c.drawString(
        6 * mm,
        8 * mm,
        "Отсканируйте QR-код для проверки гарантии",
    )


    c.showPage()
    c.save()
    return buffer.getvalue()