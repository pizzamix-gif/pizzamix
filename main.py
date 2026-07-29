import asyncio
import logging
import sys

import aiohttp
from aiohttp import web

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

import config
import database
import seed_data
from handlers_admin import router as admin_router
from handlers_user import router as user_router
from middlewares import LoggingMiddleware

logging.basicConfig(level=logging.INFO, stream=sys.stdout)
logger = logging.getLogger("mix_bot")

bot = Bot(token=config.BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())

logging_mw = LoggingMiddleware()
dp.message.middleware(logging_mw)
dp.callback_query.middleware(logging_mw)

# Admin router first: it has its own ADMIN_IDS filter, so this ordering
# only matters for /admin vs. any (unlikely) overlapping command names.
dp.include_router(admin_router)
dp.include_router(user_router)

pool = None

PING_INTERVAL_SECONDS = 10 * 60  # stay under Render free tier's 15-minute sleep timer


async def self_ping_loop() -> None:
    """Render's free web services spin down after ~15 minutes with no incoming
    HTTP request. This periodically hits our own public URL so that never
    happens — no external cron service needed. Only runs when we actually
    have a public URL (i.e. deployed with a webhook, not local polling)."""
    if not config.EXTERNAL_URL:
        return
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=20)) as session:
        while True:
            await asyncio.sleep(PING_INTERVAL_SECONDS)
            try:
                async with session.get(config.EXTERNAL_URL) as resp:
                    logger.info("Self-ping OK (%s)", resp.status)
            except Exception:
                logger.warning("Self-ping failed", exc_info=True)


async def on_startup(bot: Bot) -> None:
    global pool
    pool = await database.create_pool()
    await database.init_db(pool)
    await seed_data.seed_products(pool)
    dp["pool"] = pool
    logger.info("Database ready (pool created, schema ensured, menu seeded if empty).")

    if config.WEBHOOK_URL:
        await bot.set_webhook(
            url=config.WEBHOOK_URL,
            secret_token=config.WEBHOOK_SECRET_TOKEN,
            drop_pending_updates=True,
        )
        logger.info("Webhook set to %s", config.WEBHOOK_URL)
        asyncio.create_task(self_ping_loop())
        logger.info("Self-ping loop started (every %s min)", PING_INTERVAL_SECONDS // 60)


async def on_shutdown(bot: Bot) -> None:
    if pool is not None:
        await pool.close()
    if config.WEBHOOK_URL:
        await bot.delete_webhook()
    logger.info("Shutdown complete.")


async def health(request: web.Request) -> web.Response:
    return web.Response(text="OK")


def main() -> None:
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    if not config.WEBHOOK_URL:
        # No public URL available (e.g. running locally) — fall back to
        # long polling so you can still test the bot without deploying it.
        logger.warning("WEBHOOK_URL/RENDER_EXTERNAL_URL not set — using long polling (local dev only).")
        asyncio.run(dp.start_polling(bot))
        return

    app = web.Application()
    app.router.add_get("/", health)  # Render's health check hits this

    SimpleRequestHandler(
        dispatcher=dp, bot=bot, secret_token=config.WEBHOOK_SECRET_TOKEN
    ).register(app, path=config.WEBHOOK_PATH)

    setup_application(app, dp, bot=bot)
    web.run_app(app, host="0.0.0.0", port=config.PORT)


if __name__ == "__main__":
    main()
