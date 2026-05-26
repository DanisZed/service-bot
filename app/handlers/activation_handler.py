"""Обработчик активации во втором боте"""

import os
from typing import Tuple, Optional, List

from app.db.session import AsyncSessionLocal
from app.db.models import Master
from sqlalchemy import select


def _inline_keyboard(rows: List[List[dict]]) -> List[dict]:
    return [{
        "type": "inline_keyboard",
        "payload": {"buttons": rows},
    }]


async def handle_activation_start(user_id: int, payload: str) -> Tuple[str, Optional[List[dict]]]:
    """Обработка перехода по ссылке активации"""
    
    # Парсим payload: activate_master_id
    if payload.startswith("activate_"):
        master_id = payload.replace("activate_", "")
        
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(Master).where(Master.master_id == master_id)
            )
            master = result.scalar_one_or_none()
            
            if not master:
                return "❌ Ошибка: мастер не найден. Обратитесь к администратору.", None
            
            # Активируем мастера
            master.is_active = 1
            await session.commit()
            
            # Формируем сообщение об успехе
            role_text = "Администратор" if master.is_admin else "Мастер"
            name_text = master.service_name or master.name or ""
            
            # Ссылка на первого бота (Диспетчер)
            first_bot_username = os.getenv("MAX_FIRST_BOT_USERNAME", "dispetcher_bot")
            first_bot_link = f"https://max.ru/{first_bot_username}"
            
            kb = _inline_keyboard([[
                {
                    "type": "link",
                    "text": "✅ Завершить регистрацию",
                    "url": first_bot_link,
                }
            ]])
            
            text = (
                f"✅ **Активация прошла успешно!**\n\n"
                f"👤 Роль: {role_text}\n"
                f"📛 {name_text}\n"
                f"🆔 ID: `{master.master_id}`\n\n"
                f"Теперь вы можете вернуться в первый бот и начать работу.\n\n"
                f"Нажмите «Завершить регистрацию», чтобы продолжить."
            )
            
            return text, kb
    
    return "❌ Неверная ссылка активации.", None


async def handle_activation_confirmation(user_id: int) -> Tuple[str, Optional[List[dict]]]:
    """Подтверждение активации после возврата в первый бот"""
    
    # Проверяем, активен ли пользователь
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Master).where(
                Master.max_user_id == user_id,
                Master.is_active == 1
            )
        )
        master = result.scalar_one_or_none()
        
        if master:
            role_text = "Администратор" if master.is_admin else "Мастер"
            name_text = master.service_name or master.name or ""
            
            text = (
                f"🎉 **Добро пожаловать!**\n\n"
                f"✅ Ваша учетная запись активирована.\n"
                f"👤 Роль: {role_text}\n"
                f"📛 {name_text}\n\n"
                f"Теперь вы можете создавать заявки.\n"
                f"Напишите /start, чтобы начать работу."
            )
            return text, None
        else:
            return "❌ Ваша учетная запись не найдена или не активирована. Пройдите регистрацию заново.", None