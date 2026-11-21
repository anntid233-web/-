#!/usr/bin/env python3
"""
Proxy Shop Telegram Bot
Main entry point.
"""

import asyncio
import logging
import sys
from config import config
from database import init_db
from handlers import bot


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("bot.log", encoding="utf-8")
    ]
)

logger = logging.getLogger(__name__)


async def setup_webhook():
    """Setup webhook if configured."""
    if config.WEBHOOK_URL:
        webhook_url = f"{config.WEBHOOK_URL}/webhook"
        await bot.remove_webhook()
        await bot.set_webhook(url=webhook_url)
        logger.info(f"Webhook set to {webhook_url}")


async def run_polling():
    """Run bot in polling mode."""
    logger.info("Starting bot in polling mode...")
    
    # Remove webhook if any
    await bot.remove_webhook()
    
    # Start polling
    await bot.infinity_polling(
        timeout=30,
        long_polling_timeout=30,
        allowed_updates=["message", "callback_query", "inline_query"]
    )


async def run_webhook():
    """Run bot with webhook (requires aiohttp server)."""
    from aiohttp import web
    
    async def handle_webhook(request):
        if request.headers.get("X-Telegram-Bot-Api-Secret-Token") != config.BOT_TOKEN.split(":")[1]:
            return web.Response(status=403)
        
        data = await request.json()
        await bot.process_new_updates([data])
        return web.Response(status=200)
    
    app = web.Application()
    app.router.add_post("/webhook", handle_webhook)
    
    await setup_webhook()
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", config.WEBHOOK_PORT)
    await site.start()
    
    logger.info(f"Webhook server started on port {config.WEBHOOK_PORT}")
    
    # Keep running
    try:
        await asyncio.Event().wait()
    finally:
        await runner.cleanup()


async def main():
    """Main function."""
    # Validate config
    if not config.BOT_TOKEN:
        logger.error("BOT_TOKEN not set in environment variables!")
        sys.exit(1)
    
    if not config.ADMIN_IDS:
        logger.warning("ADMIN_IDS not set - admin panel will be unavailable")
    
    # Initialize database
    await init_db()
    logger.info("Database initialized")
    
    # Get bot info
    me = await bot.get_me()
    logger.info(f"Bot started: @{me.username} ({me.first_name})")
    
    # Run bot
    if config.WEBHOOK_URL:
        await run_webhook()
    else:
        await run_polling()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)