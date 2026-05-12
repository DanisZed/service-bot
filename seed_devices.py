from __future__ import annotations

import asyncio

from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.db.models import DeviceCategory, DeviceSubtype


async def seed_devices() -> None:
    categories_data = [
        {
            "name": "Крупная бытовая техника",
            "code": "major_appliance",
            "sort_order": 10,
            "subtypes": [
                {"name": "Стиральные машины", "code": "washing_machine", "sort_order": 10},
                {"name": "Сушильные машины", "code": "dryer", "sort_order": 20},
                {"name": "Водонагреватели", "code": "water_heater", "sort_order": 30},
            ],
        },
        {
            "name": "Кухонная техника",
            "code": "kitchen_appliance",
            "sort_order": 20,
            "subtypes": [
                {"name": "Посудомоечные машины", "code": "dishwasher", "sort_order": 10},
                {"name": "Духовые шкафы", "code": "oven", "sort_order": 20},
                {"name": "Варочные поверхности электрические", "code": "hob_electric", "sort_order": 30},
                {"name": "Варочные поверхности индукционные", "code": "hob_induction", "sort_order": 40},
                {"name": "Микроволновые печи", "code": "microwave", "sort_order": 50},
                {"name": "Кухонные комбайны", "code": "food_processor", "sort_order": 60},
                {"name": "Мясорубки", "code": "meat_grinder", "sort_order": 70},
                {"name": "Миксеры/блендеры", "code": "mixer_blender", "sort_order": 80},
            ],
        },
        {
            "name": "Электрика / силовое оборудование / инструмент",
            "code": "power_equipment",
            "sort_order": 30,
            "subtypes": [
                {"name": "Стабилизаторы", "code": "stabilizer", "sort_order": 10},
                {"name": "Сварочные аппараты", "code": "welder", "sort_order": 20},
                {"name": "Электроинструменты", "code": "power_tool", "sort_order": 30},
            ],
        },
        {
            "name": "Мелкая бытовая и уборка",
            "code": "small_appliance",
            "sort_order": 40,
            "subtypes": [
                {"name": "Пылесосы", "code": "vacuum", "sort_order": 10},
                {"name": "Фены", "code": "hair_dryer", "sort_order": 20},
                {"name": "И другое", "code": "other", "sort_order": 90},
            ],
        },
    ]

    async with AsyncSessionLocal() as session:
        # Проверяем, сидили ли уже
        result = await session.execute(select(DeviceCategory))
        existing_categories = result.scalars().all()

        if existing_categories:
            print(f"Найдено уже {len(existing_categories)} категорий, сид пропускаем.")
            return

        print("Сидим категории и типы техники...")

        for cat in categories_data:
            category = DeviceCategory(
                code=cat["code"],           # ВАЖНО
                name=cat["name"],
                sort_order=cat["sort_order"],
            )
            session.add(category)

            for st in cat["subtypes"]:
                subtype = DeviceSubtype(
                    code=st["code"],               # ВАЖНО
                    category_code=cat["code"],     # ВАЖНО
                    name=st["name"],
                    sort_order=st["sort_order"],
                )
                session.add(subtype)

        await session.commit()
        print("Сидинг завершён.")


if __name__ == "__main__":
    asyncio.run(seed_devices())