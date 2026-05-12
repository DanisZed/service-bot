from __future__ import annotations

from typing import List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import DeviceCategory, DeviceSubtype


async def list_categories(session: AsyncSession) -> List[DeviceCategory]:
    """
    Вернуть все категории техники.
    При необходимости можно добавить фильтр по is_active и сортировку.
    """
    stmt = select(DeviceCategory).order_by(DeviceCategory.name)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def list_subtypes_by_category(
    session: AsyncSession,
    category_code: str,
) -> List[DeviceSubtype]:
    """
    Вернуть все подтипы техники по коду категории.

    ВАЖНО: здесь предполагается, что у DeviceSubtype есть поле category_code.
    Если у тебя поле называется иначе (например, main_category или category_id),
    нужно заменить фильтр ниже на правильное поле.
    """
    stmt = (
        select(DeviceSubtype)
        .where(DeviceSubtype.category_code == category_code)
        .order_by(DeviceSubtype.name)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())