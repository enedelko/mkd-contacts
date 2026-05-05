"""
Telegram bot entry point (aiogram 3.x, webhook mode).
"""
import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web

from app.config import (
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_SOCKS5_PROXY,
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
        try:
            info = await bot.get_webhook_info()
        except Exception as e:
            logger.warning("getWebhookInfo failed: %s", e)
        else:
            logger.info(
                "WebhookInfo pending_update_count=%s max_connections=%s",
                info.pending_update_count,
                getattr(info, "max_connections", None),
            )
            if info.last_error_message:
                logger.warning(
                    "Telegram getWebhookInfo last_error_message (входящая доставка на URL, не SOCKS): %s",
                    info.last_error_message,
                )
            logger.info(
                "Проверка getWebhookInfo вручную (токен в лог не выводим; подставьте из .env или export): "
                'curl -sS "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/getWebhookInfo"'
            )
            if TELEGRAM_SOCKS5_PROXY:
                logger.info(
                    "Тот же запрос через SOCKS как у бота: "
                    'curl -sS -x "${TELEGRAM_SOCKS5_PROXY}" '
                    '"https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/getWebhookInfo"'
                )
    else:
        logger.warning("WEBHOOK_HOST not set, skipping webhook registration")


async def on_shutdown(bot: Bot):
    await backend_client.close()
    await bot.delete_webhook()
    logger.info("Webhook deleted, bot shut down")


def main():
    storage = SQLiteStorage(db_path=SESSION_DB_PATH, ttl_seconds=SESSION_TTL_SECONDS)
    props = DefaultBotProperties(parse_mode=ParseMode.HTML)
    if TELEGRAM_SOCKS5_PROXY:
        session = AiohttpSession(proxy=TELEGRAM_SOCKS5_PROXY)
        bot = Bot(token=TELEGRAM_BOT_TOKEN, session=session, default=props)
        logger.info("Telegram Bot API client uses SOCKS5 proxy (TELEGRAM_SOCKS5_PROXY is set)")
    else:
        bot = Bot(token=TELEGRAM_BOT_TOKEN, default=props)
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
