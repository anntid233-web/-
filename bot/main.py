import asyncio
import logging
import sys
from contextlib import asynccontextmanager

import telebot
from telebot import asyncio_helper
from aiohttp import web

from config import config
from database import init_db, AsyncSessionLocal, User, UserRole
from handlers.user_handlers import register_user_handlers, register_text_handlers
from handlers.admin_handlers import register_admin_handlers, register_admin_text_handlers
from webhook import setup_webhook


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("bot.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)

# Reduce telebot logging
logging.getLogger("telebot").setLevel(logging.WARNING)
logging.getLogger("aiohttp").setLevel(logging.WARNING)


# Global bot instance
bot = telebot.AsyncTeleBot(config.BOT_TOKEN)


async def setup_bot():
    """Initialize bot and register handlers"""
    # Initialize database
    await init_db()
    logger.info("Database initialized")

    # Ensure admins exist in DB
    async with AsyncSessionLocal() as session:
        for admin_id in config.ADMIN_IDS:
            admin = await session.get(User, admin_id)
            if not admin:
                admin = User(
                    id=admin_id,
                    role=UserRole.ADMIN,
                    referral_code=f"admin_{admin_id}",
                )
                session.add(admin)
            elif admin.role != UserRole.ADMIN:
                admin.role = UserRole.ADMIN
        await session.commit()

    # Register handlers
    register_user_handlers(bot)
    register_text_handlers(bot)
    register_admin_handlers(bot)
    register_admin_text_handlers(bot)

    # Set bot commands
    await bot.set_my_commands([
        telebot.types.BotCommand("start", "🏠 Главное меню"),
        telebot.types.BotCommand("menu", "📋 Меню"),
        telebot.types.BotCommand("profile", "👤 Профиль"),
        telebot.types.BotCommand("myproxies", "📦 Мои прокси"),
        telebot.types.BotCommand("balance", "💰 Баланс"),
        telebot.types.BotCommand("help", "ℹ️ Помощь"),
    ])

    logger.info("Bot handlers registered")


async def delete_webhook():
    """Delete webhook if using polling"""
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        logger.info("Webhook deleted")
    except Exception as e:
        logger.warning(f"Failed to delete webhook: {e}")


async def run_polling():
    """Run bot in polling mode"""
    await setup_bot()
    await delete_webhook()

    logger.info("Starting polling...")
    try:
        await bot.infinity_polling(
            timeout=30,
            long_polling_timeout=30,
            allowed_updates=["message", "callback_query", "chat_member"],
        )
    except Exception as e:
        logger.error(f"Polling error: {e}")
        raise


async def run_webhook():
    """Run bot with webhook"""
    await setup_bot()

    # Create aiohttp app
    app = web.Application()
    setup_webhook(app)

    # Set webhook
    webhook_url = f"https://{config.WEBHOOK_HOST}{config.WEBHOOK_PATH}"
    try:
        await bot.set_webhook(webhook_url, drop_pending_updates=True)
        logger.info(f"Webhook set to {webhook_url}")
    except Exception as e:
        logger.error(f"Failed to set webhook: {e}")
        raise

    # Run web server
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", config.WEBHOOK_PORT)
    await site.start()
    logger.info(f"Webhook server started on port {config.WEBHOOK_PORT}")

    # Keep running
    try:
        await asyncio.Event().wait()
    except KeyboardInterrupt:
        pass
    finally:
        await runner.cleanup()
        await bot.delete_webhook()


async def main():
    """Main entry point"""
    if not config.BOT_TOKEN:
        logger.error("BOT_TOKEN not set in environment!")
        sys.exit(1)

    if not config.YOOKASSA_SHOP_ID or not config.YOOKASSA_SECRET_KEY:
        logger.warning("YooKassa credentials not set! Payments will not work.")

    if not config.PROXY6_API_KEY:
        logger.warning("Proxy6 API key not set! Proxy purchasing will not work.")

    if config.WEBHOOK_HOST:
        await run_webhook()
    else:
        await run_polling()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped")
    except Exception as e:
        logger.exception(f"Fatal error: {e}")
        sys.exit(1)