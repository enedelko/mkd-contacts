"""
Telegram bot entry point (aiogram 3.x, webhook mode).
"""
import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web

from app.config import (
    TELEGRAM_BOT_TOKEN,
    LISTEN_PORT,
    WEBHOOK_HOST,
    WEBHOOK_PATH,
    SESSION_DB_PATH,
    SESSION_TTL_SECONDS,
)
from app.storage.sqlite_storage import SQLiteStorage
from app.handlers import start, premises, survey, contact, mydata, notifications
from app import backend_client

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


async def on_startup(bot: Bot):
    if WEBHOOK_HOST:
        url = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"
        await bot.set_webhook(url)
        logger.info("Webhook set to %s", url)
    else:
        logger.warning("WEBHOOK_HOST not set, skipping webhook registration")


async def on_shutdown(bot: Bot):
    await backend_client.close()
    await bot.delete_webhook()
    logger.info("Webhook deleted, bot shut down")


def main():
    storage = SQLiteStorage(db_path=SESSION_DB_PATH, ttl_seconds=SESSION_TTL_SECONDS)
    bot = Bot(token=TELEGRAM_BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=storage)

    # Роутеры с state-специфичными обработчиками (в т.ч. «Отмена» из ENTER_PARKING_INPUT) — раньше start
    dp.include_router(notifications.router)
    dp.include_router(premises.router)
    dp.include_router(survey.router)
    dp.include_router(contact.router)
    dp.include_router(mydata.router)
    dp.include_router(start.router)

    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    app = web.Application()
    handler = SimpleRequestHandler(dispatcher=dp, bot=bot)
    handler.register(app, path=WEBHOOK_PATH)
    setup_application(app, dp, bot=bot)

    logger.info("Starting bot on port %s, webhook path %s", LISTEN_PORT, WEBHOOK_PATH)
    web.run_app(app, host="0.0.0.0", port=LISTEN_PORT)


if __name__ == "__main__":
    main()
