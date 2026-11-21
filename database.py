import aiosqlite
from contextlib import asynccontextmanager
from config import config
import os


SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    first_name TEXT,
    last_name TEXT,
    balance REAL DEFAULT 0,
    referral_code TEXT UNIQUE,
    referred_by INTEGER,
    total_spent REAL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_banned INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS proxies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ip TEXT NOT NULL,
    port INTEGER NOT NULL,
    username TEXT,
    password TEXT,
    country TEXT,
    city TEXT,
    isp TEXT,
    type TEXT DEFAULT 'http',  -- http, https, socks4, socks5
    price_per_day REAL DEFAULT 0,
    price_per_week REAL DEFAULT 0,
    price_per_month REAL DEFAULT 0,
    status TEXT DEFAULT 'available',  -- available, sold, reserved, expired
    seller_id INTEGER,
    expires_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS purchases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    proxy_id INTEGER NOT NULL,
    duration_days INTEGER NOT NULL,
    price REAL NOT NULL,
    status TEXT DEFAULT 'active',  -- active, expired, cancelled
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NOT NULL,
    auto_renew INTEGER DEFAULT 0,
    FOREIGN KEY (user_id) REFERENCES users(user_id),
    FOREIGN KEY (proxy_id) REFERENCES proxies(id)
);

CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    amount REAL NOT NULL,
    type TEXT NOT NULL,  -- deposit, purchase, refund, referral_bonus, withdrawal
    status TEXT DEFAULT 'pending',  -- pending, completed, failed, cancelled
    payment_id TEXT,
    payment_provider TEXT,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    description TEXT
);

CREATE INDEX IF NOT EXISTS idx_proxies_status ON proxies(status);
CREATE INDEX IF NOT EXISTS idx_purchases_user ON purchases(user_id);
CREATE INDEX IF NOT EXISTS idx_transactions_user ON transactions(user_id);
"""


async def init_db():
    """Initialize database and create tables."""
    os.makedirs(os.path.dirname(config.DATABASE_PATH), exist_ok=True)
    async with aiosqlite.connect(config.DATABASE_PATH) as db:
        await db.executescript(SCHEMA)
        await db.commit()
        
        # Insert default settings
        default_settings = [
            ("welcome_message", "👋 Добро пожаловать в Proxy Shop Bot!\n\nЗдесь вы можете купить качественные прокси для любых задач.", "Приветственное сообщение"),
            ("proxy_types", "http,https,socks4,socks5", "Доступные типы прокси"),
            ("countries", "RU,US,DE,FR,NL,GB,CA,AU,JP,SG", "Доступные страны"),
        ]
        for key, value, desc in default_settings:
            await db.execute(
                "INSERT OR IGNORE INTO settings (key, value, description) VALUES (?, ?, ?)",
                (key, value, desc)
            )
        await db.commit()


@asynccontextmanager
async def get_db():
    """Get database connection."""
    async with aiosqlite.connect(config.DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        yield db


# User operations
async def get_or_create_user(user_id: int, username: str = None, first_name: str = None, last_name: str = None, referred_by: int = None):
    async with get_db() as db:
        cursor = await db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        user = await cursor.fetchone()
        
        if not user:
            import secrets
            referral_code = secrets.token_urlsafe(8)
            await db.execute(
                """INSERT INTO users (user_id, username, first_name, last_name, referral_code, referred_by)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (user_id, username, first_name, last_name, referral_code, referred_by)
            )
            await db.commit()
            cursor = await db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
            user = await cursor.fetchone()
        else:
            # Update user info
            await db.execute(
                """UPDATE users SET username = ?, first_name = ?, last_name = ?, updated_at = CURRENT_TIMESTAMP
                   WHERE user_id = ?""",
                (username, first_name, last_name, user_id)
            )
            await db.commit()
        
        return user


async def get_user(user_id: int):
    async with get_db() as db:
        cursor = await db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        return await cursor.fetchone()


async def update_balance(user_id: int, amount: float):
    async with get_db() as db:
        await db.execute(
            "UPDATE users SET balance = balance + ?, updated_at = CURRENT_TIMESTAMP WHERE user_id = ?",
            (amount, user_id)
        )
        await db.commit()


async def get_user_by_referral_code(code: str):
    async with get_db() as db:
        cursor = await db.execute("SELECT * FROM users WHERE referral_code = ?", (code,))
        return await cursor.fetchone()


# Proxy operations
async def add_proxy(ip: str, port: int, country: str, city: str = None, isp: str = None,
                    proxy_type: str = "http", username: str = None, password: str = None,
                    price_per_day: float = 0, price_per_week: float = 0, price_per_month: float = 0,
                    seller_id: int = None):
    async with get_db() as db:
        cursor = await db.execute(
            """INSERT INTO proxies (ip, port, username, password, country, city, isp, type,
                   price_per_day, price_per_week, price_per_month, seller_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (ip, port, username, password, country, city, isp, proxy_type,
             price_per_day, price_per_week, price_per_month, seller_id)
        )
        await db.commit()
        return cursor.lastrowid


async def get_available_proxies(country: str = None, proxy_type: str = None, limit: int = 50):
    async with get_db() as db:
        query = "SELECT * FROM proxies WHERE status = 'available'"
        params = []
        if country:
            query += " AND country = ?"
            params.append(country)
        if proxy_type:
            query += " AND type = ?"
            params.append(proxy_type)
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        cursor = await db.execute(query, params)
        return await cursor.fetchall()


async def get_proxy(proxy_id: int):
    async with get_db() as db:
        cursor = await db.execute("SELECT * FROM proxies WHERE id = ?", (proxy_id,))
        return await cursor.fetchone()


async def reserve_proxy(proxy_id: int, user_id: int):
    async with get_db() as db:
        await db.execute(
            "UPDATE proxies SET status = 'reserved', seller_id = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ? AND status = 'available'",
            (user_id, proxy_id)
        )
        await db.commit()
        cursor = await db.execute("SELECT * FROM proxies WHERE id = ?", (proxy_id,))
        return await cursor.fetchone()


async def sell_proxy(proxy_id: int):
    async with get_db() as db:
        await db.execute(
            "UPDATE proxies SET status = 'sold', updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (proxy_id,)
        )
        await db.commit()


async def release_proxy(proxy_id: int):
    async with get_db() as db:
        await db.execute(
            "UPDATE proxies SET status = 'available', seller_id = NULL, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (proxy_id,)
        )
        await db.commit()


async def get_user_proxies(user_id: int, active_only: bool = True):
    async with get_db() as db:
        query = """
            SELECT p.*, pur.expires_at, pur.duration_days, pur.auto_renew
            FROM proxies p
            JOIN purchases pur ON p.id = pur.proxy_id
            WHERE pur.user_id = ?
        """
        if active_only:
            query += " AND pur.status = 'active' AND pur.expires_at > CURRENT_TIMESTAMP"
        query += " ORDER BY pur.expires_at DESC"
        cursor = await db.execute(query, (user_id,))
        return await cursor.fetchall()


# Purchase operations
async def create_purchase(user_id: int, proxy_id: int, duration_days: int, price: float):
    from datetime import datetime, timedelta
    expires_at = datetime.now() + timedelta(days=duration_days)
    async with get_db() as db:
        cursor = await db.execute(
            """INSERT INTO purchases (user_id, proxy_id, duration_days, price, expires_at)
               VALUES (?, ?, ?, ?, ?)""",
            (user_id, proxy_id, duration_days, price, expires_at)
        )
        await db.commit()
        return cursor.lastrowid


async def get_purchase(purchase_id: int):
    async with get_db() as db:
        cursor = await db.execute("SELECT * FROM purchases WHERE id = ?", (purchase_id,))
        return await cursor.fetchone()


async def extend_purchase(purchase_id: int, additional_days: int):
    async with get_db() as db:
        await db.execute(
            "UPDATE purchases SET expires_at = datetime(expires_at, '+' || ? || ' days') WHERE id = ?",
            (additional_days, purchase_id)
        )
        await db.commit()


# Transaction operations
async def create_transaction(user_id: int, amount: float, type_: str, payment_provider: str = None,
                             payment_id: str = None, description: str = None):
    async with get_db() as db:
        cursor = await db.execute(
            """INSERT INTO transactions (user_id, amount, type, payment_provider, payment_id, description)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (user_id, amount, type_, payment_provider, payment_id, description)
        )
        await db.commit()
        return cursor.lastrowid


async def complete_transaction(transaction_id: int):
    async with get_db() as db:
        await db.execute(
            "UPDATE transactions SET status = 'completed', completed_at = CURRENT_TIMESTAMP WHERE id = ?",
            (transaction_id,)
        )
        await db.commit()


async def get_user_transactions(user_id: int, limit: int = 20):
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT * FROM transactions WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
            (user_id, limit)
        )
        return await cursor.fetchall()


# Settings
async def get_setting(key: str):
    async with get_db() as db:
        cursor = await db.execute("SELECT value FROM settings WHERE key = ?", (key,))
        row = await cursor.fetchone()
        return row["value"] if row else None


async def set_setting(key: str, value: str):
    async with get_db() as db:
        await db.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
            (key, value)
        )
        await db.commit()


# Stats
async def get_stats():
    async with get_db() as db:
        stats = {}
        cursor = await db.execute("SELECT COUNT(*) as count FROM users")
        stats["total_users"] = (await cursor.fetchone())["count"]
        cursor = await db.execute("SELECT COUNT(*) as count FROM proxies WHERE status = 'available'")
        stats["available_proxies"] = (await cursor.fetchone())["count"]
        cursor = await db.execute("SELECT COUNT(*) as count FROM proxies WHERE status = 'sold'")
        stats["sold_proxies"] = (await cursor.fetchone())["count"]
        cursor = await db.execute("SELECT SUM(amount) as total FROM transactions WHERE type = 'deposit' AND status = 'completed'")
        row = await cursor.fetchone()
        stats["total_revenue"] = row["total"] or 0
        return stats