# scripts/test_webpush.py
import asyncio
import json
from datetime import datetime, timezone

from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.db.models import WebPushSubscription
from app.services.webpush_sender import send_webpush


async def main():
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(WebPushSubscription).order_by(WebPushSubscription.id.desc()).limit(1)
        )
        sub = result.scalar_one_or_none()

        if not sub:
            print("Нет подписок в webpush_subscription. Сначала подпишись с фронта.")
            return

        payload = {
            "title": "Тестовое уведомление",
            "body": f"Время: {datetime.now(timezone.utc).isoformat(timespec='seconds')}",
            "url": "/app/mobile-requests",
        }

        ok = send_webpush(sub, payload)
        print("send_webpush result:", ok)


if __name__ == "__main__":
    asyncio.run(main())