"""Сервис регистрации пользователей в Max боте (Диспетчер)"""

from __future__ import annotations

import os
import random
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from app.db.session import AsyncSessionLocal
from app.db.models import Master
from sqlalchemy import select


def generate_master_id() -> str:
    """Генерирует master_id формата МСТР + 7 цифр"""
    digits = ''.join(str(random.randint(0, 9)) for _ in range(7))
    return f"МСТР{digits}"


def generate_service_id() -> str:
    """Генерирует service_id формата СРВС + 6 цифр"""
    digits = ''.join(str(random.randint(0, 9)) for _ in range(6))
    return f"СРВС{digits}"


def normalize_phone(raw: str) -> Optional[str]:
    """Нормализует номер телефона к формату +7XXXXXXXXXX"""
    digits = "".join(ch for ch in raw if ch.isdigit())
    if len(digits) == 11 and (digits.startswith("7") or digits.startswith("8")):
        return "+7" + digits[1:]
    if len(digits) == 11 and digits.startswith("9"):
        return "+7" + digits
    if len(digits) == 10 and digits.startswith("9"):
        return "+7" + digits
    return None


class RegistrationState:
    """Состояния регистрации"""
    CHOOSE_ROLE = "choose_role"
    # Администратор
    ADMIN_SERVICE_NAME = "admin_service_name"
    ADMIN_NAME = "admin_name"
    ADMIN_LASTNAME = "admin_lastname"
    ADMIN_PHONE = "admin_phone"
    # Мастер
    MASTER_NAME = "master_name"
    MASTER_LASTNAME = "master_lastname"
    MASTER_PHONE = "master_phone"


@dataclass
class RegistrationContext:
    """Контекст регистрации пользователя"""
    state: str = RegistrationState.CHOOSE_ROLE
    role: Optional[str] = None
    # Для админа
    service_name: Optional[str] = None
    admin_name: Optional[str] = None
    # Для мастера
    master_name: Optional[str] = None
    # Общие
    lastname: Optional[str] = None
    phone: Optional[str] = None
    generated_master_id: Optional[str] = None
    generated_service_id: Optional[str] = None


class RegistrationService:
    """Сервис для регистрации пользователей в первом боте (Диспетчер)"""
    
    def __init__(self):
        self._sessions: Dict[int, RegistrationContext] = {}
    
    def _get_ctx(self, user_id: int) -> RegistrationContext:
        if user_id not in self._sessions:
            print(f"🆕 Новый контекст регистрации для user_id={user_id}")
            self._sessions[user_id] = RegistrationContext()
        else:
            print(f"📌 Существующий контекст для user_id={user_id}, state={self._sessions[user_id].state}")
        return self._sessions[user_id]
    
    def reset(self, user_id: int) -> None:
        print(f"🗑️ Сброс контекста регистрации для user_id={user_id}")
        self._sessions.pop(user_id, None)
    
    def is_in_registration(self, user_id: int) -> bool:
        """Проверяет, находится ли пользователь в процессе регистрации"""
        ctx = self._sessions.get(user_id)
        if not ctx:
            return False
        return ctx.state != RegistrationState.CHOOSE_ROLE
    
    def _inline_keyboard(self, rows: List[List[dict]]) -> List[dict]:
        return [{
            "type": "inline_keyboard",
            "payload": {"buttons": rows},
        }]
    
    async def start_registration(self, user_id: int) -> Tuple[str, Optional[List[dict]]]:
        """Начало регистрации — показываем кнопку начала"""
        
        # Если уже в процессе регистрации — продолжаем
        if self.is_in_registration(user_id):
            return await self._continue_registration(user_id)
        
        # Создаем новый контекст
        self.reset(user_id)
        ctx = self._get_ctx(user_id)
        ctx.state = RegistrationState.CHOOSE_ROLE
        
        kb = self._inline_keyboard([[
            {
                "type": "callback",
                "text": "🚀 Начать регистрацию",
                "payload": "registration:start",
                "intent": "default",
            }
        ]])
        
        welcome_text = (
            "👋 Добро пожаловать в сервис-бот Max (Диспетчер)!\n\n"
            "Здесь вы сможете:\n"
            "✅ Создавать и отправлять заявки мастерам\n"
            "✅ Отслеживать статус выполнения\n"
            "✅ Получать уведомления\n\n"
            "Для начала работы необходимо зарегистрироваться."
        )
        
        return welcome_text, kb
    
    async def _continue_registration(self, user_id: int) -> Tuple[str, Optional[List[dict]]]:
        """Продолжает регистрацию с текущего состояния"""
        ctx = self._get_ctx(user_id)
        
        if ctx.role == "admin":
            if ctx.state == RegistrationState.ADMIN_SERVICE_NAME and ctx.service_name:
                ctx.state = RegistrationState.ADMIN_NAME
                return "Отлично! Теперь введите ваше имя:", None
            elif ctx.state == RegistrationState.ADMIN_NAME and ctx.admin_name:
                ctx.state = RegistrationState.ADMIN_LASTNAME
                return "Хорошо! Теперь введите вашу фамилию:", None
            elif ctx.state == RegistrationState.ADMIN_LASTNAME and ctx.lastname:
                ctx.state = RegistrationState.ADMIN_PHONE
                return "Теперь введите ваш номер телефона:\nФормат: +7XXXXXXXXXX или 8XXXXXXXXXX", None
        elif ctx.role == "master":
            if ctx.state == RegistrationState.MASTER_NAME and ctx.master_name:
                ctx.state = RegistrationState.MASTER_LASTNAME
                return "Теперь введите вашу фамилию:", None
            elif ctx.state == RegistrationState.MASTER_LASTNAME and ctx.lastname:
                ctx.state = RegistrationState.MASTER_PHONE
                return "Теперь введите ваш номер телефона:\nФормат: +7XXXXXXXXXX или 8XXXXXXXXXX", None
        
        # Если не можем продолжить — начинаем заново с выбором роли
        ctx.state = RegistrationState.CHOOSE_ROLE
        return self._show_role_choice()
    
    async def handle_callback(self, user_id: int, payload: str) -> Tuple[str, Optional[List[dict]]]:
        """Обработка callback-запросов"""
        ctx = self._get_ctx(user_id)
        
        print(f"🔔 registration callback: user_id={user_id}, payload={payload}, state={ctx.state}")
        
        if payload == "registration:start":
            ctx.state = RegistrationState.CHOOSE_ROLE
            return self._show_role_choice()
        
        if payload == "role:admin":
            ctx.role = "admin"
            ctx.generated_master_id = generate_master_id()
            ctx.generated_service_id = generate_service_id()
            ctx.state = RegistrationState.ADMIN_SERVICE_NAME
            return (
                f"📋 Регистрация Администратора\n\n"
                f"Ваш ID мастера: `{ctx.generated_master_id}`\n"
                f"ID сервиса: `{ctx.generated_service_id}`\n\n"
                f"Введите название вашего сервиса/компании:",
                None
            )
        
        if payload == "role:master":
            ctx.role = "master"
            ctx.generated_master_id = generate_master_id()
            ctx.state = RegistrationState.MASTER_NAME
            return (
                f"📋 Регистрация Мастера\n\n"
                f"Ваш ID мастера: `{ctx.generated_master_id}`\n\n"
                f"Введите ваше имя:",
                None
            )
        
        return "Неизвестная команда. Попробуйте /start", None
    
    async def handle_message(self, user_id: int, text: str) -> Tuple[str, Optional[List[dict]]]:
        """Обработка текстовых сообщений"""
        ctx = self._get_ctx(user_id)
        text_clean = text.strip()
        
        print(f"🔔 registration message: user_id={user_id}, state={ctx.state}, text={text_clean}")
        
        if text_clean.lower() in ("/cancel", "отмена", "стоп"):
            self.reset(user_id)
            return "❌ Регистрация отменена. Чтобы начать заново, напишите /start", None
        
        # АДМИНИСТРАТОР
        if ctx.state == RegistrationState.ADMIN_SERVICE_NAME:
            ctx.service_name = text_clean
            ctx.state = RegistrationState.ADMIN_NAME
            return "Отлично! Теперь введите ваше имя:", None
        
        if ctx.state == RegistrationState.ADMIN_NAME:
            ctx.admin_name = text_clean
            ctx.state = RegistrationState.ADMIN_LASTNAME
            return "Хорошо! Теперь введите вашу фамилию:", None
        
        if ctx.state == RegistrationState.ADMIN_LASTNAME:
            ctx.lastname = text_clean
            ctx.state = RegistrationState.ADMIN_PHONE
            return "Теперь введите ваш номер телефона:\nФормат: +7XXXXXXXXXX или 8XXXXXXXXXX", None
        
        if ctx.state == RegistrationState.ADMIN_PHONE:
            phone = normalize_phone(text_clean)
            if not phone:
                return "❌ Неверный формат номера. Введите номер в формате +7XXXXXXXXXX или 8XXXXXXXXXX", None
            ctx.phone = phone
            return await self._complete_registration(user_id, ctx)
        
        # МАСТЕР
        if ctx.state == RegistrationState.MASTER_NAME:
            ctx.master_name = text_clean
            ctx.state = RegistrationState.MASTER_LASTNAME
            return f"Приятно познакомиться, {ctx.master_name}!\n\nТеперь введите вашу фамилию:", None
        
        if ctx.state == RegistrationState.MASTER_LASTNAME:
            ctx.lastname = text_clean
            ctx.state = RegistrationState.MASTER_PHONE
            return f"Спасибо, {ctx.master_name} {ctx.lastname}!\n\nТеперь введите ваш номер телефона:\nФормат: +7XXXXXXXXXX или 8XXXXXXXXXX", None
        
        if ctx.state == RegistrationState.MASTER_PHONE:
            phone = normalize_phone(text_clean)
            if not phone:
                return "❌ Неверный формат номера. Введите номер в формате +7XXXXXXXXXX или 8XXXXXXXXXX", None
            ctx.phone = phone
            return await self._complete_registration(user_id, ctx)
        
        # Если состояние не определено — показываем кнопку начала
        return await self.start_registration(user_id)
    
    async def _complete_registration(self, user_id: int, ctx: RegistrationContext) -> Tuple[str, Optional[List[dict]]]:
        """Сохраняет в БД (is_active=0) и показывает кнопку для перехода во второй бот"""
        
        async with AsyncSessionLocal() as session:
            real_max_user_id = user_id
            
            result = await session.execute(
                select(Master).where(Master.max_user_id == real_max_user_id)
            )
            existing = result.scalar_one_or_none()
            
            if existing:
                master = existing
                master.master_id = ctx.generated_master_id
                master.name = ctx.master_name if ctx.role == "master" else ctx.admin_name
                master.lastname = ctx.lastname
                master.service_name = ctx.service_name if ctx.role == "admin" else None
                master.phone = ctx.phone
                master.is_active = 0
                master.is_admin = 1 if ctx.role == "admin" else 0
            else:
                master = Master(
                    master_id=ctx.generated_master_id,
                    max_user_id=real_max_user_id,
                    name=ctx.master_name if ctx.role == "master" else ctx.admin_name,
                    lastname=ctx.lastname,
                    service_name=ctx.service_name if ctx.role == "admin" else None,
                    phone=ctx.phone,
                    plan="free",
                    is_active=0,
                    is_admin=1 if ctx.role == "admin" else 0,
                    created_at=datetime.now(),
                    max_chat_id=user_id,
                )
                session.add(master)
            
            await session.commit()
        
        order_bot_link = os.getenv("MAX_ORDER_BOT_LINK", "https://max.ru/id027308840424_1_bot")
        activate_link = f"{order_bot_link}?start=activate_{ctx.generated_master_id}"
        
        kb = self._inline_keyboard([[
            {
                "type": "link",
                "text": "✅ Активировать бота",
                "url": activate_link,
            }
        ]])
        
        if ctx.role == "admin":
            text = (
                f"📝 Регистрация Администратора создана!\n\n"
                f"🏢 Сервис: {ctx.service_name}\n"
                f"👤 Имя: {ctx.admin_name}\n"
                f"👤 Фамилия: {ctx.lastname}\n"
                f"🆔 ID мастера: `{ctx.generated_master_id}`\n"
                f"🆔 ID сервиса: `{ctx.generated_service_id}`\n"
                f"📞 Телефон: {ctx.phone}\n\n"
                f"⚠️ **Для активации нажмите кнопку «Активировать бота»**"
            )
        else:
            text = (
                f"📝 Регистрация Мастера создана!\n\n"
                f"👤 Имя: {ctx.master_name}\n"
                f"👤 Фамилия: {ctx.lastname}\n"
                f"🆔 ID мастера: `{ctx.generated_master_id}`\n"
                f"📞 Телефон: {ctx.phone}\n\n"
                f"⚠️ **Для активации нажмите кнопку «Активировать бота»**"
            )
        
        self.reset(user_id)
        return text, kb
    
    def _show_role_choice(self) -> Tuple[str, List[dict]]:
        """Показывает выбор роли"""
        kb = self._inline_keyboard([
            [
                {
                    "type": "callback",
                    "text": "👑 Администратор",
                    "payload": "role:admin",
                    "intent": "default",
                }
            ],
            [
                {
                    "type": "callback",
                    "text": "🔧 Мастер",
                    "payload": "role:master",
                    "intent": "default",
                }
            ]
        ])
        
        text = (
            "🎯 **Выберите вашу роль**\n\n"
            "**Администратор** — управление сервисом, просмотр всех заявок\n"
            "**Мастер** — выполнение заявок, работа с клиентами\n\n"
            "Кто вы?"
        )
        
        return text, kb


registration_service = RegistrationService()