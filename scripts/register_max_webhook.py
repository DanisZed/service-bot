import asyncio
import httpx

ACCESS_TOKEN = "f9LHodD0cOJ-w1SxNh6DvVYwGrJbfhmqPq0biXFVWO5XtzC11k02pcl_qhAIIu9hG51oJ4mDqMrRioKNBkks"

async def main():
    url = "https://platform-api.max.ru/subscriptions"
    payload = {
        "url": "https://service.daniszed.keenetic.pro/max/webhook",
        "update_types": ["message_created", "message_callback", "bot_started"],
        "secret": "danis_super_secret_key_1",
    }
    headers = {
        # ВАЖНО: без Bearer, просто сам токен
        "Authorization": ACCESS_TOKEN,
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(url, json=payload, headers=headers)
        print("Status:", resp.status_code)
        print("Body:", resp.text)

if __name__ == "__main__":
    asyncio.run(main())