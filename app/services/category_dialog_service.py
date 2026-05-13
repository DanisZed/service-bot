from __future__ import annotations

from typing import Tuple, List

from app.services.dialog_state import dialog_state_store
from app.services.devices import list_categories, list_subtypes_by_category
from app.services.max_keyboards import make_categories_keyboard, make_subtypes_keyboard
from app.services.old_dialog_service import dialog_service as old_dialog_service
from app.db.session import AsyncSessionLocal


class CategoryDialogService:
    """
    Первый этап диалога: выбор категории и вида техники.

    Сценарий:
      1) /start → показываем категорию
      2) пользователь выбирает категорию (cat:<code>)
      3) показываем подтипы (виды техники)
      4) пользователь выбирает подтип (sub:<code>)
      5) автоматически создаём "услугу" для старого диалога и
         переводим его сразу в состояние ADDRESS_MODE (выбор мастерская/адрес)

    На этом этапе пользователь НИЧЕГО не вводит текстом – только нажимает кнопки.
    """

    async def handle_message(self, user_id: int, text: str) -> Tuple[str, List[dict]]:
        """
        На этапе категорий текст игнорируем и всегда показываем/повторяем клавиатуру.
        """
        chat_id = user_id
        state = dialog_state_store.get(user_id, chat_id)
        step = state.get("step")

        # Если диалог категорий ещё не начат – стартуем с категорий
        if not step or step == "choose_category":
            return await self._start_new_dialog(user_id, chat_id)

        # Если уже выбраны категория/подтип – текст обрабатывает старый диалог
        return await old_dialog_service.handle_message(user_id, text)

    async def handle_callback(self, user_id: int, payload: str) -> Tuple[str, List[dict] | None]:
        chat_id = user_id
        state = dialog_state_store.get(user_id, chat_id)
        step = state.get("step")

        # Выбор категории
        if payload.startswith("cat:"):
            category_code = payload.split(":", 1)[1]
            return await self._handle_category_chosen(user_id, chat_id, category_code)

        # Выбор подтипа
        if payload.startswith("sub:"):
            subtype_code = payload.split(":", 1)[1]
            return await self._handle_subtype_chosen(user_id, chat_id, subtype_code)

        # Всё остальное (address_mode, slots, ...) отдаём старому диалогу
        return await old_dialog_service.handle_callback(user_id, payload)

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
        dialog_state_store.update(
            user_id,
            chat_id,
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
        """
        Когда пользователь выбрал подтип:
          - сохраняем main_category и subtype в глобальном состоянии
          - инициализируем старый DialogContext:
              * service = "<подтип>" (пока упрощённо по коду)
              * state = ADDRESS_MODE (сразу спрашиваем, мастерская или адрес)
          - отправляем первый вопрос старого диалога.
        """
        # Сохраняем подтип в общем состоянии (на случай, если пригодится)
        dialog_state_store.update(
            user_id,
            chat_id,
            step="category_finished",
            subtype=subtype_code,
        )

        # Инициализируем старый диалог
        service_title = f"{subtype_code}"
        ctx = old_dialog_service._get_ctx(user_id)
        ctx.service = service_title

        # ВАЖНО: используем то же состояние, что и старый диалог
        # предполагаем, что в old_dialog_service есть константа ADDRESS_MODE
        ctx.state = old_dialog_service.ADDRESS_MODE

        text = (
            f"Записал: {service_title}.\n"
            "Где выполнить услугу?\n"
            "— Нажми «Мастерская», если привезёшь сам\n"
            "— Нажми «Ввести адрес», чтобы ввести адрес вручную\n"
            "Или просто отправь адрес текстом."
        )
        kb = old_dialog_service._buttons_address_mode()
        return text, kb


category_dialog_service = CategoryDialogService()