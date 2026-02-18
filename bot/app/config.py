"""Bot configuration loaded from environment variables."""
import os

TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
BACKEND_URL = os.getenv("BACKEND_URL", "http://backend:8000")
BOT_API_TOKEN = os.environ["BOT_API_TOKEN"]
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")
WEBHOOK_PATH = f"/api/tg-wh/{WEBHOOK_SECRET}" if WEBHOOK_SECRET else "/api/tg-wh/hook"
WEBHOOK_HOST = os.getenv("WEBHOOK_HOST", "")
LISTEN_PORT = int(os.getenv("BOT_PORT", "8443"))
SESSION_DB_PATH = os.getenv("SESSION_DB_PATH", "/data/sessions.db")
SESSION_TTL_SECONDS = int(os.getenv("SESSION_TTL_SECONDS", "3600"))
