# app/services/max_commands.py

from typing import Any, Dict, Optional, Tuple, List
import os
import httpx
from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.db.models import Master

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")


async def _get_login_url_for_max_user(max_user_id: int) -> str:
    """Вызывает backend /api/master/auth/request-code-by-max и возвращает login_url"""
    url = f"{API_BASE_URL}/api/master/auth/request-code-by-max"
    async with httpx.AsyncClient(timeout=5.0) as client:
        resp = await client.post(url, params={"max_user_id": max_user_id})
    resp.raise_for_status()
    data = resp.json()
    return data["login_url"]


async def handle_complete_registration(master_id: str, user_id: int) -> Tuple[str, Optional[List[Dict[str, Any]]]]:
    """Обработка завершения регистрации после активации"""
    
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Master).where(Master.master_id == master_id, Master.is_active == 1)
        )
        master = result.scalar_one_or_none()
    
    if not master:
        return "❌ Ошибка: регистрация не завершена. Попробуйте снова.", None
    
    # Формируем кнопку "Новая заявка"
    kb = [{
        "type": "inline_keyboard",
        "payload": {
            "buttons": [[{
                "type": "callback",
                "text": "📝 Новая заявка",
                "payload": "menu:new_request",
                "intent": "default",
            }]]
        }
    }]
    
    role_text = "Администратор" if master.is_admin else "Мастер"
    name_text = master.name or master.service_name or ""
    
    reply_text = (
        f"🎉 **Регистрация успешно завершена!**\n\n"
        f"👤 Роль: {role_text}\n"
        f"📛 {name_text}\n"
        f"🆔 ID мастера: `{master.master_id}`\n\n"
        f"Теперь вы можете создавать заявки.\n\n"
        f"Нажмите «Новая заявка», чтобы начать."
    )
    
    return reply_text, kb


async def handle_command(
    user_id: int,
    text: str,
    payload: str = None,  # Добавляем параметр payload из bot_started
) -> Tuple[Optional[str], Optional[List[Dict[str, Any]]]]:
    
    # ========== ОБРАБОТКА ДИПЛИНКА С ПАРАМЕТРОМ ==========
    if payload and payload.startswith("complete_"):
        master_id = payload.replace("complete_", "")
        return await handle_complete_registration(master_id, user_id)
    
    # ========== ОБЫЧНЫЕ КОМАНДЫ ==========
    lower = text.strip().lower() if text else ""

    if lower == "/panel":
        link = await _get_login_url_for_max_user(user_id)

        reply_text = (
            "Откройте панель мастера по кнопке ниже.\n\n"
            "Мы авторизуем вас автоматически по вашему аккаунту MAX."
        )

        buttons_rows: List[List[dict]] = [
            [
                {
                    "type": "link",
                    "text": "Открыть панель мастера",
                    "url": link,
                }
            ]
        ]

        attachments: List[Dict[str, Any]] = [
            {
                "type": "inline_keyboard",
                "payload": {"buttons": buttons_rows},
            }
        ]

        return reply_text, attachments

    return None, None

async def cmd_sticker(user_id: int, args: list):
    if len(args) < 1:
        return "Используйте: /sticker <ID заявки>", None
    try:
        req_id = int(args[0])
    except:
        return "ID заявки должен быть числом", None

    async with AsyncSessionLocal() as session:
        req = await session.get(ServiceRequest, req_id)
        if not req:
            return "Заявка не найдена", None
        master = await session.execute(select(Master).where(Master.max_user_id == user_id))
        master = master.scalar_one_or_none()
        if not master or (req.master_id != master.id and req.assigned_master_id != master.id):
            return "Нет доступа к этой заявке", None

        owner = await session.get(Master, req.master_id)
        service_name = owner.service_center.service_name if owner.service_center else None
        frontend_base = os.getenv("PANEL_BASE_URL", "https://panel.master-rbt-crm.ru")
        qr_url = f"{frontend_base}/requests/{req_id}?master_id={owner.id}&service_center_id={owner.service_center_id or ''}"

        img_bytes = await generate_sticker(
            request_id=req_id,
            service_name=service_name,
            master_lastname=owner.lastname or "",
            master_name=owner.name or "",
            created_at=req.created_at,
            qr_url=qr_url,
        )

    # Отправляем изображение через MAX API
    from max_client import MaxClient
    client = MaxClient()
    try:
        # Метод send_image предполагает, что вы загрузите файл
        # Реализуйте upload и отправку картинки
        # Временно дадим ссылку на эндпоинт
        api_base = os.getenv("API_BASE_URL", "https://panel.master-rbt-crm.ru")
        sticker_url = f"{api_base}/api/requests/{req_id}/sticker"
        return f"Наклейка для заявки {req_id}:\n{sticker_url}", None
    finally:
        await client.close()