from __future__ import annotations

from typing import Tuple, List

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal
from app.services.dialog_state import dialog_state_store
from app.services.devices import list_categories, list_subtypes_by_category
from app.services.max_keyboards import make_categories_keyboard, make_subtypes_keyboard
from app.services.requests import create_service_request


class DialogService:
    """
    Простой диалоговый сервис для MAX.

    Шаги:
      1) Сначала показываем категории (choose_category)
      2) Потом подтипы (choose_subtype)
      3) Потом спрашиваем описание (ask_problem)
      4) Потом спрашиваем тип локации (choose_location)
      5) Потом, при необходимости, адрес (ask_address)
      6) В конце создаём ServiceRequest и подтверждаем (finished)
    """

    async def handle_message(self, user_id: int, text: str) -> Tuple[str, List[dict]]:
        """
        Обработка обычного сообщения (message_created).
        Здесь, в зависимости от текущего step, трактуем текст как:
          - описание проблемы
          - адрес
          - что-то ещё
        """
        # Для простоты считаем, что chat_id == user_id (если в MAX отдельно есть chat_id – потом добавим)
        chat_id = user_id
        state = dialog_state_store.get(user_id, chat_id)
        step = state.get("step")

        # Если диалог не начат — показываем выбор категории
        if not step:
            return await self._start_new_dialog(user_id, chat_id)

        # В зависимости от шага:
        if step == "ask_problem":
            return await self._handle_problem_description(user_id, chat_id, text)
        elif step == "ask_address":
            return await self._handle_address(user_id, chat_id, text)

        # Если пришёл текст в неожиданном шаге — просто повторим текущий вопрос
        return "Пожалуйста, используйте кнопки на экране.", []

    async def handle_callback(self, user_id: int, payload: str) -> Tuple[str, List[dict] | None]:
        """
        Обработка нажатия кнопок (message_callback).
        payload может быть:
          - "cat:<code>"
          - "sub:<code>"
          - "loc:workshop"
          - "loc:client_address"
        """
        chat_id = user_id
        state = dialog_state_store.get(user_id, chat_id)
        step = state.get("step")

        if payload.startswith("cat:"):
            category_code = payload.split(":", 1)[1]
            return await self._handle_category_chosen(user_id, chat_id, category_code)

        if payload.startswith("sub:"):
            subtype_code = payload.split(":", 1)[1]
            return await self._handle_subtype_chosen(user_id, chat_id, subtype_code)

        if payload.startswith("loc:"):
            loc = payload.split(":", 1)[1]
            return await self._handle_location_chosen(user_id, chat_id, loc)

        # Неизвестный payload
        return "Команда не распознана.", None

    # --- Внутренние шаги ---

    async def _start_new_dialog(self, user_id: int, chat_id: int) -> Tuple[str, List[dict]]:
        dialog_state_store.set(user_id, chat_id, {"step": "choose_category"})

        async with AsyncSessionLocal() as session:
            categories = await list_categories(session)

        kb = make_categories_keyboard(categories)
        text = "Выберите категорию техники:"
        return text, kb

    async def _handle_category_chosen(
        self,
        user_id: int,
        chat_id: int,
        category_code: str,
    ) -> Tuple[str, List[dict]]:
        # Сохраняем основную категорию и переходим к выбору подтипа
        dialog_state_store.update(
            user_id, chat_id,
            step="choose_subtype",
            main_category=category_code,
        )

        async with AsyncSessionLocal() as session:
            subtypes = await list_subtypes_by_category(session, category_code)

        kb = make_subtypes_keyboard(subtypes)
        text = "Выберите вид техники:"
        return text, kb

    async def _handle_subtype_chosen(
        self,
        user_id: int,
        chat_id: int,
        subtype_code: str,
    ) -> Tuple[str, List[dict] | None]:
        # Сохраняем subtype и просим описать проблему
        dialog_state_store.update(
            user_id, chat_id,
            step="ask_problem",
            subtype=subtype_code,
        )

        text = "Кратко опишите проблему:"
        # attachments=None — оставляем текущую клавиатуру/чистим? Тут вернём пустой список, чтобы MAX убрал клаву
        return text, []

    async def _handle_problem_description(
        self,
        user_id: int,
        chat_id: int,
        text: str,
    ) -> Tuple[str, List[dict]]:
        # Сохраняем описание и просим выбрать тип локации
        dialog_state_store.update(
            user_id, chat_id,
            step="choose_location",
            problem_description=text,
        )

        # Собираем клавиатуру выбора локации
        kb = [
            {
                "type": "inline_keyboard",
                "payload": {
                    "buttons": [
                        [
                            {
                                "type": "callback",
                                "text": "Привезу в мастерскую",
                                "payload": "loc:workshop",
                            }
                        ],
                        [
                            {
                                "type": "callback",
                                "text": "Нужен выезд мастера",
                                "payload": "loc:client_address",
                            }
                        ],
                    ]
                },
            }
        ]
        return "Где удобнее выполнить ремонт?", kb

    async def _handle_location_chosen(
        self,
        user_id: int,
        chat_id: int,
        location_type: str,
    ) -> Tuple[str, List[dict] | None]:
        if location_type == "workshop":
            # Для мастерской адрес можно не спрашивать, сразу создаём заявку
            dialog_state_store.update(
                user_id, chat_id,
                step="finalize",
                location_type="workshop",
            )
            return await self._finalize_request(user_id, chat_id)
        else:
            # Для выезда нужно спросить адрес
            dialog_state_store.update(
                user_id, chat_id,
                step="ask_address",
                location_type="client_address",
            )
            return "Пожалуйста, отправьте адрес, куда нужно приехать:", []

    async def _handle_address(
        self,
        user_id: int,
        chat_id: int,
        address: str,
    ) -> Tuple[str, List[dict]]:
        dialog_state_store.update(
            user_id, chat_id,
            address=address,
            step="finalize",
        )
        return await self._finalize_request(user_id, chat_id)

    async def _finalize_request(
        self,
        user_id: int,
        chat_id: int,
    ) -> Tuple[str, List[dict]]:
        state = dialog_state_store.get(user_id, chat_id)

        data = {
            "user_id": user_id,
            "chat_id": chat_id,
            "client_id": None,
            "client_name": state.get("client_name"),
            "client_phone": state.get("client_phone"),
            "main_category": state["main_category"],
            "subtype": state["subtype"],
            "custom_device": state.get("custom_device"),
            "service_title": state.get("service_title"),
            "problem_description": state["problem_description"],
            "location_type": state["location_type"],
            "address": state.get("address"),
            "address_details": state.get("address_details"),
            "date_iso": state.get("date_iso"),
            "time_slot": state.get("time_slot"),
            "datetime_from": state.get("datetime_from"),
            "datetime_to": state.get("datetime_to"),
            "total_amount": state.get("total_amount"),
            "currency": state.get("currency", "RUB"),
            "payment_status": state.get("payment_status", "unpaid"),
            "meta": state.get("meta"),
        }

        async with AsyncSessionLocal() as session:
            req = await create_service_request(session, data)

        dialog_state_store.clear(user_id, chat_id)

        text = f"Заявка создана ✅\nНомер: {req.id}"
        # attachments=[] — убираем клавиатуру
        return text, []

# Экземпляр сервиса для импорта в max_webhook.py
dialog_service = DialogService()