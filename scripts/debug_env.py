from pathlib import Path
import os

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
env_path = BASE_DIR / ".env"

print("ENV PATH:", env_path)
print("EXISTS:", env_path.exists())

load_dotenv(env_path)

print("SECRET_KEY:", os.getenv("SECRET_KEY"))
print("MAX_BOT_TOKEN:", os.getenv("MAX_BOT_TOKEN"))
print("MAX_APPLICATIONS_CHAT_ID:", os.getenv("MAX_APPLICATIONS_CHAT_ID"))