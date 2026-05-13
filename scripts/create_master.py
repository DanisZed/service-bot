import asyncio
from datetime import datetime

from app.db.session import AsyncSessionLocal
from app.db.models import Master


YOUR_MAX_USER_ID = 123456789  # <-- сюда вставь СВОЙ user_id во втором боте
YOUR_NAME = "Данис"           # опционально
YOUR_PHONE = None             # опционально
YOUR_EMAIL = None             # опционально


async def main():
    async with AsyncSessionLocal() as session:
        # проверим, нет ли уже мастера с таким max_user_id
        existing = await session.execute(
            Master.__table__.select().where(Master.max_user_id == YOUR_MAX_USER_ID)
        )
        row = existing.first()
        if row:
            print("Master with this max_user_id already exists:", row[0].id)
            return

        master = Master(
            max_user_id=YOUR_MAX_USER_ID,
            max_chat_id=None,
            name=YOUR_NAME,
            phone=YOUR_PHONE,
            email=YOUR_EMAIL,
            plan="free",
            is_active=1,
            created_at=datetime.utcnow(),
        )

        session.add(master)
        await session.commit()
        await session.refresh(master)
        print("Created master with id:", master.id)


if __name__ == "__main__":
    asyncio.run(main())