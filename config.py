import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass
class Config:
    # Bot
    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
    ADMIN_IDS: list[int] = list(map(int, filter(None, os.getenv("ADMIN_IDS", "").split(","))))
    
    # Database
    DATABASE_PATH: str = os.getenv("DATABASE_PATH", "data/bot.db")
    
    # Payment (example: CryptoBot, YooMoney, etc.)
    PAYMENT_PROVIDER: str = os.getenv("PAYMENT_PROVIDER", "cryptobot")  # cryptobot, yoomoney, etc.
    CRYPTOBOT_TOKEN: str = os.getenv("CRYPTOBOT_TOKEN", "")
    YOOMONEY_TOKEN: str = os.getenv("YOOMONEY_TOKEN", "")
    YOOMONEY_WALLET: str = os.getenv("YOOMONEY_WALLET", "")
    
    # Proxy provider API (if using external provider)
    PROXY_API_URL: str = os.getenv("PROXY_API_URL", "")
    PROXY_API_KEY: str = os.getenv("PROXY_API_KEY", "")
    
    # Bot settings
    SUPPORT_USERNAME: str = os.getenv("SUPPORT_USERNAME", "@support")
    REFERRAL_BONUS_PERCENT: int = int(os.getenv("REFERRAL_BONUS_PERCENT", "10"))
    MIN_DEPOSIT: float = float(os.getenv("MIN_DEPOSIT", "1.0"))
    
    # Webhook (optional)
    WEBHOOK_URL: str = os.getenv("WEBHOOK_URL", "")
    WEBHOOK_PORT: int = int(os.getenv("WEBHOOK_PORT", "8443"))


config = Config()