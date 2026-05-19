# scripts/seed_devices.py
# перед первым запуском выполнить посев в БД:
# cd /home/servicebot/service-bot
# PYTHONPATH=. python scripts/seed_devices.py
import asyncio

from app.db.session import AsyncSessionLocal
from app.db.models import DeviceCategory, DeviceSubtype


CATEGORIES = [
    # код, название, sort_order
    ("major_appliance", "Крупная бытовая техника", 10),
    ("kitchen", "Плиты, СВЧ, духовки", 20),
    ("small_kitchen_appliance", "Мелкая кухонная техника", 30),
    ("small_appliance", "Мелкая бытовая техника", 40),
    ("equipment", "Электроприборы и инструменты", 50),
    ("climate", "Климатическая техника", 60),
]

SUBTYPES = [
    # --- Крупная бытовая техника ---
    ("washing_machine", "Стиральные машины", "major_appliance", 10),
    ("dishwasher", "Посудомоечные машины", "major_appliance", 20),
    ("dryer", "Сушильные машины", "major_appliance", 30),
    ("water_heater", "Водонагреватели", "major_appliance", 40),
    ("fridge", "Холодильники и морозильники", "major_appliance", 50),

    # --- Кухонная техника ---
    ("oven", "Электрические духовки", "kitchen", 10),
    ("cooking_surface", "Электрические плиты", "kitchen", 20),
    ("microwave", "Микроволновые печи", "kitchen", 30),

    # --- Электроприборы и инструменты ---
    ("welding", "Сварочные аппараты", "equipment", 10),
    ("stabilizer_ups", "Стабилизаторы и бесперебойники", "equipment", 20),
    ("power_tools", "Электроинструмент", "equipment", 30),

    # --- Климатическая техника ---
    ("heater", "Обогреватели", "climate", 10),
    ("air_conditioner", "Кондиционеры", "climate", 20),

    # --- Мелкая кухонная техника ---
    ("kitchen_iron_steamer", "Отпариватели и утюги", "small_kitchen_appliance", 10),
    ("kitchen_mixer_blender", "Миксеры и блендеры", "small_kitchen_appliance", 20),
    ("meat_grinder_processor", "Мясорубки и комбайны", "small_kitchen_appliance", 30),
    ("baker_multicooker", "Хлебопечи и мультиварки", "small_kitchen_appliance", 40),

    # --- Мелкая бытовая техника ---
    ("home_iron_steamer", "Парогенераторы и утюги", "small_appliance", 10),
    ("vacuum", "Пылесосы", "small_appliance", 20),
    ("hair_care", "Фены и стайлеры", "small_appliance", 30),
    ("humidifier", "Увлажнители", "small_appliance", 40),
]


async def seed():
    async with AsyncSessionLocal() as session:
        # 1. Обновляем/создаём категории
        for code, name, order in CATEGORIES:
            obj = await session.get(DeviceCategory, code)
            if obj is None:
                obj = DeviceCategory(code=code, name=name, sort_order=order)
                session.add(obj)
            else:
                obj.name = name
                obj.sort_order = order

        # 2. Чистим старые подтипы и создаём новые
        await session.execute(DeviceSubtype.__table__.delete())

        for code, name, cat_code, order in SUBTYPES:
            st = DeviceSubtype(
                code=code,
                name=name,
                category_code=cat_code,
                sort_order=order,
            )
            session.add(st)

        await session.commit()
        print("OK: categories & subtypes updated")


if __name__ == "__main__":
    asyncio.run(seed())