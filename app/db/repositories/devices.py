from typing import List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import DeviceCategory, DeviceSubtype


async def list_categories(session: AsyncSession) -> List[DeviceCategory]:
    stmt = (
        select(DeviceCategory)
        .order_by(DeviceCategory.sort_order, DeviceCategory.code)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def list_subtypes_by_category(
    session: AsyncSession,
    category_code: str,
) -> List[DeviceSubtype]:
    stmt = (
        select(DeviceSubtype)
        .where(DeviceSubtype.category_code == category_code)
        .order_by(DeviceSubtype.sort_order, DeviceSubtype.code)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())