import asyncio
import httpx

MAX_API_BASE_URL = "https://platform-api.max.ru"

MAX_BOT_TOKEN = "f9LHodD0cOJ-w1SxNh6DvVYwGrJbfhmqPq0biXFVWO5XtzC11k02pcl_qhAIIu9hG51oJ4mDqMrRioKNBkks"
CHANNEL_CHAT_ID = -74626173921476  # твой канал


async def main():
    async with httpx.AsyncClient(
        base_url=MAX_API_BASE_URL,
        headers={
            "Authorization": MAX_BOT_TOKEN,
            "Content-Type": "application/json",
        },
        timeout=10.0,
    ) as client:
        payload = {
            "recipient": {
                "chat_id": CHANNEL_CHAT_ID,
            },
            "message": {
                "text": "Тест из отдельного скрипта в канал",
            },
        }

        try:
            resp = await client.post("/messages", json=payload)
        except httpx.HTTPError as e:
            print("HTTP error:", repr(e))
            return

        print("Status code:", resp.status_code)
        print("Response text:", resp.text)


if __name__ == "__main__":
    asyncio.run(main())