import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
ADMIN_ID = os.getenv("ADMIN_ID")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID")
YOOMONEY_ACCESS_TOKEN = os.getenv("YOOMONEY_ACCESS_TOKEN")
YOOMONEY_WALLET = os.getenv("YOOMONEY_WALLET")

WEBHOOK_MODE = os.getenv("WEBHOOK_MODE", "False").lower() == "true"
PORT = int(os.getenv("PORT", 10000))
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "").rstrip('/')
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")

MIN_DEPOSIT = int(os.getenv("MIN_DEPOSIT", 2))
MAX_DEPOSIT = int(os.getenv("MAX_DEPOSIT", 100000))

if not TELEGRAM_TOKEN:
    raise ValueError("Необходимо указать TELEGRAM_TOKEN в .env файле")
if not YOOMONEY_WALLET:
    raise ValueError("Необходимо указать YOOMONEY_WALLET в .env файле")

MIN_BET = int(os.getenv("MIN_BET", 1))
MAX_BET = int(os.getenv("MAX_BET", 100000))
MIN_WITHDRAWAL = int(os.getenv("MIN_WITHDRAWAL", 500))
