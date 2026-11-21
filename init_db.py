#!/usr/bin/env python3
"""Initialize database with sample data."""

import asyncio
import sys
sys.path.insert(0, '.')

from config import config
from database import init_db, add_proxy, set_setting


async def main():
    print("🔧 Initializing database...")
    await init_db()
    print("✅ Database initialized")
    
    # Add sample proxies
    sample_proxies = [
        # (ip, port, country, city, type, price_day, price_week, price_month)
        ("45.12.34.56", 8080, "RU", "Moscow", "http", 15, 90, 300),
        ("45.12.34.57", 8080, "RU", "Moscow", "https", 20, 120, 400),
        ("45.12.34.58", 1080, "RU", "St. Petersburg", "socks5", 25, 150, 500),
        ("185.23.45.67", 8080, "US", "New York", "http", 20, 120, 400),
        ("185.23.45.68", 8080, "US", "Los Angeles", "https", 25, 150, 500),
        ("185.23.45.69", 1080, "US", "Chicago", "socks5", 30, 180, 600),
        ("194.32.12.34", 8080, "DE", "Frankfurt", "http", 18, 100, 350),
        ("194.32.12.35", 1080, "DE", "Berlin", "socks5", 28, 160, 550),
        ("178.23.45.67", 8080, "NL", "Amsterdam", "http", 18, 100, 350),
        ("178.23.45.68", 1080, "NL", "Rotterdam", "socks5", 28, 160, 550),
        ("51.89.12.34", 8080, "FR", "Paris", "http", 20, 120, 400),
        ("51.89.12.35", 1080, "FR", "Lyon", "socks5", 30, 180, 600),
    ]
    
    print("📦 Adding sample proxies...")
    for proxy in sample_proxies:
        try:
            await add_proxy(
                ip=proxy[0], port=proxy[1], country=proxy[2], city=proxy[3],
                proxy_type=proxy[4], price_per_day=proxy[5],
                price_per_week=proxy[6], price_per_month=proxy[7]
            )
        except Exception as e:
            print(f"  ⚠️ Failed to add {proxy[0]}:{proxy[1]} - {e}")
    
    print("✅ Sample proxies added")
    
    # Update settings
    await set_setting("welcome_message", 
        "👋 <b>Добро пожаловать в Proxy Shop Bot!</b>\n\n"
        "🛒 Здесь вы можете купить качественные прокси для любых задач:\n"
        "• Парсинг и скрейпинг\n"
        "• Социальные сети и мессенджеры\n"
        "• Обход блокировок\n"
        "• Анонимный серфинг\n\n"
        "💰 Пополните баланс и выбирайте прокси в каталоге!")
    
    await set_setting("countries", "RU,US,DE,NL,FR,GB,CA,AU,JP,SG")
    await set_setting("proxy_types", "http,https,socks4,socks5")
    
    print("✅ Settings updated")
    print("\n🎉 Initialization complete! Run the bot with: python main.py")


if __name__ == "__main__":
    asyncio.run(main())