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
        
        # Формируем ссылку на фронт для завершения регистрации
        panel_base_url = os.getenv("PANEL_BASE_URL", "https://panel.master-rbt-crm.ru")
        complete_link = f"{panel_base_url}/register?code=complete_{master.master_id}"
        
        kb = [{
            "type": "inline_keyboard",
            "payload": {
                "buttons": [[{
                    "type": "link",
                    "text": "✅ Завершить регистрацию",
                    "url": complete_link,
                }]]
            }
        }]

        text = (
            f"✅ **Активация прошла успешно!**\n\n"
            f"👤 Роль: {role_text}\n"
            f"📛 {name_text}\n"
            f"🆔 ID мастера: `{master.master_id}`\n\n"
            f"Нажмите «Завершить регистрацию», чтобы войти в панель управления."
        )
        
        return text, kb


@router.post("/order/webhook")
async def order_webhook(request: Request, background_tasks: BackgroundTasks) -> Dict[str, Any]:
    """Webhook для order_bot"""
    
    body = await request.json()
    print("\n" + "="*60)
    print("🔔 ORDER BOT WEBHOOK")
    print(f"update_type: {body.get('update_type')}")
    print(f"body: {body}")
    print("="*60 + "\n")
    
    logger.info(f"Order bot webhook: {body}")
    
    update_type = body.get("update_type")
    
    if update_type == "bot_started":
        user = body.get("user", {})
        user_id = user.get("user_id")
        payload = body.get("payload")
        
        print(f"🔔 bot_started: user_id={user_id}, payload={payload}")
        
        if payload and payload.startswith("activate_"):
            master_id = payload.replace("activate_", "")
            print(f"🔔 Активируем мастера: {master_id}")
            
            reply_text, attachments = await activate_master(master_id, user_id)
            print(f"🔔 Ответ: {reply_text[:100]}...")
            
            client = MaxOrderBotClient()
            try:
                await client.send_text_to_user(
                    user_id=user_id,
                    text=reply_text,
                    attachments=attachments,
                )
                print("🔔 Сообщение отправлено!")
            except Exception as e:
                print(f"🔔 Ошибка отправки: {e}")
            finally:
                await client.close()
        else:
            print(f"🔔 payload не начинается с activate_: {payload}")
    else:
        print(f"🔔 update_type не bot_started: {update_type}")
    
    return {"success": True}