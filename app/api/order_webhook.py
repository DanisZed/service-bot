"""Webhook для order_bot — активация мастеров и получение заявок"""

import logging
import os
from typing import Dict, Any, Optional, List, Tuple

from fastapi import APIRouter, Request, BackgroundTasks

from app.db.session import AsyncSessionLocal
from app.db.models import Master
from sqlalchemy import select
from max_client import MaxOrderBotClient

logger = logging.getLogger(__name__)

router = APIRouter()


async def activate_master(master_id: str, user_id: int) -> Tuple[str, Optional[List[dict]]]:
    """Активирует мастера по master_id"""
    
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Master).where(Master.master_id == master_id)
        )
        master = result.scalar_one_or_none()
        
        if not master:
            return "❌ Ошибка: мастер не найден.", None
        
        master.is_active = 1
        await session.commit()
        
        role_text = "Администратор" if master.is_admin else "Мастер"
        name_text = master.name or master.service_name or ""
        
        # В функции activate_master():

        # Ссылка на первого бота с параметром activate (без master_id)
        dispatcher_bot_link = os.getenv("MAX_DISPATCHER_BOT_LINK", "https://max.ru/id027308840424_bot")
        activate_link = f"{dispatcher_bot_link}?start=activate"

        kb = [{
            "type": "inline_keyboard",
            "payload": {
                "buttons": [[{
                    "type": "link",
                    "text": "✅ Завершить регистрацию",
                    "url": activate_link,
                }]]
            }
        }]

        text = (
            f"✅ **Активация прошла успешно!**\n\n"
            f"👤 Роль: {role_text}\n"
            f"📛 {name_text}\n"
            f"🆔 ID мастера: `{master.master_id}`\n\n"
            f"Нажмите «Завершить регистрацию», чтобы вернуться в бот и начать работу."
        )
        
        return text, kb


@router.post("/order/webhook")
async def order_webhook(request: Request, background_tasks: BackgroundTasks) -> Dict[str, Any]:
    """Webhook для order_bot"""
    
    body = await request.json()
    logger.info(f"Order bot webhook: {body}")
    
    update_type = body.get("update_type")
    
    if update_type == "bot_started":
        user = body.get("user", {})
        user_id = user.get("user_id")
        payload = body.get("payload")
        
        if payload and payload.startswith("activate_"):
            master_id = payload.replace("activate_", "")
            reply_text, attachments = await activate_master(master_id, user_id)
            
            client = MaxOrderBotClient()
            try:
                await client.send_text_to_user(
                    user_id=user_id,
                    text=reply_text,
                    attachments=attachments,
                )
            finally:
                await client.close()
    
    return {"success": True}