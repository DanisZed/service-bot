#!/usr/bin/env python3
import asyncio
import httpx
import os
import sys

# Токен order_bot (второго бота) — ЗАМЕНИ НА СВОЙ ТОКЕН!
ACCESS_TOKEN = "f9LHodD0cOImIZAAElpHD9ivEWkiqgvDHDEzQoxYvcemvrNri_xMeA6jGz1Hnk0Pi29BNtBs7pOrfXfndvmS"

async def main():
    print("=" * 60)
    print("Регистрация webhook для ORDER BOT (второй бот)")
    print("=" * 60)
    
    url = "https://platform-api.max.ru/subscriptions"
    
    payload = {
        "url": "https://panel.master-rbt-crm.ru/order/webhook",
        "update_types": ["message_created", "message_callback", "bot_started"],
        "secret": "danis_super_secret_key_2",
    }
    
    headers = {
        "Authorization": ACCESS_TOKEN,
        "Content-Type": "application/json",
    }

    print(f"\n📤 Отправляем запрос в MAX API...")
    print(f"   URL: {payload['url']}")
    print(f"   Токен: {ACCESS_TOKEN[:20]}...")
    print(f"   Секрет: {payload['secret']}")
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(url, json=payload, headers=headers)
        print(f"\n📥 Ответ от MAX API:")
        print(f"   Status: {resp.status_code}")
        print(f"   Body: {resp.text}")
        
        if resp.status_code == 200:
            print("\n✅ Webhook для ORDER BOT успешно зарегистрирован!")
        elif resp.status_code == 409:
            print("\n⚠️ Webhook уже существует. Чтобы обновить, сначала удали старый.")
        else:
            print(f"\n❌ Ошибка регистрации. Код: {resp.status_code}")
            
        return resp

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"\n❌ Ошибка выполнения: {e}")
        sys.exit(1)