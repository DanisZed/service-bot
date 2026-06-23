"""Webhook для order_bot — активация мастеров и получение заявок"""

import logging
import os
from typing import Dict, Any, Optional, List, Tuple

from fastapi import APIRouter, Request, BackgroundTasks

from app.db.session import AsyncSessionLocal
from app.db.models import Master
from sqlalchemy import select
from max_client import MaxOrderBotClient
from app.services.sticker_generator import generate_sticker_for_request

logger = logging.getLogger(__name__)
router = APIRouter()


async def activate_master(master_id: str, user_id: int) -> Tuple[str, Optional[List[dict]]]:
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
        panel_base_url = os.getenv("PANEL_BASE_URL", "https://app.rbt-crm.ru")
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


# Глобальный сет для отслеживания обрабатываемых callback'ов
_processing_callbacks = set()

async def handle_callback(
    callback: Dict[str, Any],
    user_id: int,
    callback_id: str,
    payload: str
) -> None:
    if payload.startswith("sticker:"):
        if callback_id in _processing_callbacks:
            logger.warning(f"Callback {callback_id} already processing, skipping duplicate")
            return
        _processing_callbacks.add(callback_id)
        try:
            client = MaxOrderBotClient()
            try:
                await client.answer_callback(
                    callback_id=callback_id,
                    notification="⏳ Генерация гарантийного талона..."
                )
                request_id = int(payload.split(":", 1)[1])
                # Загружаем заявку, чтобы получить master_seq
                async with AsyncSessionLocal() as session:
                    from app.db.models import ServiceRequest
                    req = await session.get(ServiceRequest, request_id)
                    if not req:
                        raise ValueError("Заявка не найдена")
                    display_number = req.master_seq if req.master_seq is not None else req.id
                frontend_base = os.getenv("PANEL_BASE_URL", "https://app.rbt-crm.ru")
                logger.info(f"Generating sticker for request {request_id}, display number {display_number}, callback {callback_id}")
                pdf_bytes = await generate_sticker_for_request(request_id, frontend_base)
                await client.send_file(
                    user_id=user_id,
                    file_bytes=pdf_bytes,
                    filename=f"sticker_{display_number}.pdf",
                    caption=f"🖨️ Гарантийный талон №{display_number}",
                )
                logger.info(f"Sticker for request {request_id} (display {display_number}) sent successfully")
            except Exception as e:
                logger.error(f"Ошибка генерации/отправки наклейки: {e}")
                try:
                    await client.answer_callback(
                        callback_id=callback_id,
                        notification="❌ Ошибка генерации"
                    )
                except:
                    pass
            finally:
                await client.close()
        finally:
            _processing_callbacks.discard(callback_id)
        return

@router.post("/order/webhook")
async def order_webhook(request: Request, background_tasks: BackgroundTasks) -> Dict[str, Any]:
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
    elif update_type == "message_callback":
        callback = body.get("callback") or {}
        user = callback.get("user") or {}
        user_id = user.get("user_id")
        callback_id = callback.get("callback_id")
        payload = callback.get("payload")
        if user_id and callback_id:
            await handle_callback(callback, user_id, callback_id, payload)
        else:
            logger.warning("Invalid message_callback event: missing user_id or callback_id")
    else:
        print(f"🔔 update_type не bot_started и не message_callback: {update_type}")
    return {"success": True}