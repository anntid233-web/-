import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class Config:
    # Bot
    BOT_TOKEN: str
    ADMIN_IDS: list[int]

    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///bot.db"

    # YooKassa
    YOOKASSA_SHOP_ID: str
    YOOKASSA_SECRET_KEY: str
    YOOKASSA_WEBHOOK_SECRET: Optional[str] = None
    YOOKASSA_RETURN_URL: str = "https://t.me/your_bot_username"

    # Proxy6.net API
    PROXY6_API_KEY: str
    PROXY6_API_URL: str = "https://proxy6.net/api"

    # Bot settings
    MIN_DEPOSIT: int = 100  # rubles
    REFERRAL_BONUS: int = 50  # rubles
    PROXY_MARKUP_PERCENT: float = 0.2  # 20% markup on proxy cost

    # Webhook (optional)
    WEBHOOK_HOST: Optional[str] = None
    WEBHOOK_PORT: int = 8080
    WEBHOOK_PATH: str = "/webhook"

    @classmethod
    def from_env(cls) -> "Config":
        admin_ids_str = os.getenv("ADMIN_IDS", "")
        admin_ids = [int(x.strip()) for x in admin_ids_str.split(",") if x.strip()]

        return cls(
            BOT_TOKEN=os.getenv("BOT_TOKEN", ""),
            ADMIN_IDS=admin_ids,
            DATABASE_URL=os.getenv("DATABASE_URL", "sqlite+aiosqlite:///bot.db"),
            YOOKASSA_SHOP_ID=os.getenv("YOOKASSA_SHOP_ID", ""),
            YOOKASSA_SECRET_KEY=os.getenv("YOOKASSA_SECRET_KEY", ""),
            YOOKASSA_WEBHOOK_SECRET=os.getenv("YOOKASSA_WEBHOOK_SECRET"),
            YOOKASSA_RETURN_URL=os.getenv("YOOKASSA_RETURN_URL", "https://t.me/your_bot_username"),
            PROXY6_API_KEY=os.getenv("PROXY6_API_KEY", ""),
            PROXY6_API_URL=os.getenv("PROXY6_API_URL", "https://proxy6.net/api"),
            MIN_DEPOSIT=int(os.getenv("MIN_DEPOSIT", "100")),
            REFERRAL_BONUS=int(os.getenv("REFERRAL_BONUS", "50")),
            PROXY_MARKUP_PERCENT=float(os.getenv("PROXY_MARKUP_PERCENT", "0.2")),
            WEBHOOK_HOST=os.getenv("WEBHOOK_HOST"),
            WEBHOOK_PORT=int(os.getenv("WEBHOOK_PORT", "8080")),
            WEBHOOK_PATH=os.getenv("WEBHOOK_PATH", "/webhook"),
        )


config = Config.from_env()