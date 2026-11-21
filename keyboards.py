from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from config import config


def main_menu_keyboard(user_id: int = None):
    """Main reply keyboard."""
    kb = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    kb.add(
        KeyboardButton("🛒 Каталог прокси"),
        KeyboardButton("💼 Мои прокси"),
        KeyboardButton("💰 Баланс"),
        KeyboardButton("📊 Статистика"),
        KeyboardButton("👥 Реферальная программа"),
        KeyboardButton("ℹ️ Помощь"),
    )
    if user_id and user_id in config.ADMIN_IDS:
        kb.add(KeyboardButton("⚙️ Админ панель"))
    return kb


def catalog_keyboard():
    """Catalog inline keyboard."""
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("🌍 По странам", callback_data="catalog:countries"),
        InlineKeyboardButton("🔧 По типам", callback_data="catalog:types"),
    )
    kb.add(
        InlineKeyboardButton("🔍 Поиск", callback_data="catalog:search"),
        InlineKeyboardButton("🎲 Случайные", callback_data="catalog:random"),
    )
    kb.add(InlineKeyboardButton("⬅️ Назад", callback_data="main_menu"))
    return kb


def countries_keyboard(countries: list, page: int = 0, per_page: int = 10):
    """Countries selection keyboard."""
    kb = InlineKeyboardMarkup(row_width=2)
    start = page * per_page
    end = start + per_page
    page_countries = countries[start:end]
    
    for i in range(0, len(page_countries), 2):
        row = []
        row.append(InlineKeyboardButton(page_countries[i], callback_data=f"country:{page_countries[i]}"))
        if i + 1 < len(page_countries):
            row.append(InlineKeyboardButton(page_countries[i + 1], callback_data=f"country:{page_countries[i + 1]}"))
        kb.add(*row)
    
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("⬅️ Назад", callback_data=f"countries_page:{page - 1}"))
    if end < len(countries):
        nav.append(InlineKeyboardButton("Вперед ➡️", callback_data=f"countries_page:{page + 1}"))
    if nav:
        kb.add(*nav)
    
    kb.add(InlineKeyboardButton("⬅️ В каталог", callback_data="catalog:main"))
    return kb


def types_keyboard(types: list):
    """Proxy types keyboard."""
    kb = InlineKeyboardMarkup(row_width=2)
    for t in types:
        kb.add(InlineKeyboardButton(t.upper(), callback_data=f"type:{t}"))
    kb.add(InlineKeyboardButton("⬅️ В каталог", callback_data="catalog:main"))
    return kb


def proxy_list_keyboard(proxies: list, country: str = None, proxy_type: str = None, page: int = 0, per_page: int = 5):
    """Proxy list with pagination."""
    kb = InlineKeyboardMarkup(row_width=1)
    start = page * per_page
    end = start + per_page
    page_proxies = proxies[start:end]
    
    for proxy in page_proxies:
        price_info = []
        if proxy["price_per_day"]:
            price_info.append(f"{proxy['price_per_day']}₽/день")
        if proxy["price_per_week"]:
            price_info.append(f"{proxy['price_per_week']}₽/нед")
        if proxy["price_per_month"]:
            price_info.append(f"{proxy['price_per_month']}₽/мес")
        price_str = " | ".join(price_info) if price_info else "Цена не указана"
        
        text = f"{proxy['ip']}:{proxy['port']} ({proxy['country']}) - {price_str}"
        kb.add(InlineKeyboardButton(text, callback_data=f"proxy:{proxy['id']}"))
    
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("⬅️", callback_data=f"list_page:{page - 1}:{country or 'all'}:{proxy_type or 'all'}"))
    if end < len(proxies):
        nav.append(InlineKeyboardButton("➡️", callback_data=f"list_page:{page + 1}:{country or 'all'}:{proxy_type or 'all'}"))
    if nav:
        kb.add(*nav)
    
    kb.add(InlineKeyboardButton("⬅️ Назад", callback_data="catalog:main"))
    return kb


def proxy_detail_keyboard(proxy_id: int, user_balance: float):
    """Proxy detail with purchase options."""
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("💳 1 день", callback_data=f"buy:{proxy_id}:1"),
        InlineKeyboardButton("📅 7 дней", callback_data=f"buy:{proxy_id}:7"),
    )
    kb.add(
        InlineKeyboardButton("📆 30 дней", callback_data=f"buy:{proxy_id}:30"),
        InlineKeyboardButton("🔄 Автопродление", callback_data=f"autorenew:{proxy_id}"),
    )
    kb.add(InlineKeyboardButton("⬅️ К списку", callback_data="catalog:main"))
    return kb


def payment_keyboard(amount: float, payment_id: str, provider: str):
    """Payment keyboard."""
    kb = InlineKeyboardMarkup(row_width=1)
    if provider == "cryptobot":
        kb.add(InlineKeyboardButton(f"💎 Оплатить через CryptoBot ({amount} USDT)", url=f"https://t.me/CryptoBot?start={payment_id}"))
    elif provider == "yoomoney":
        kb.add(InlineKeyboardButton(f"💳 Оплатить через ЮMoney ({amount} RUB)", url=f"https://yoomoney.ru/quickpay/confirm.xml?receiver={config.YOOMONEY_WALLET}&sum={amount}&label={payment_id}"))
    kb.add(InlineKeyboardButton("✅ Я оплатил", callback_data=f"check_payment:{payment_id}"))
    kb.add(InlineKeyboardButton("❌ Отмена", callback_data="catalog:main"))
    return kb


def my_proxies_keyboard(proxies: list):
    """User's proxies keyboard."""
    kb = InlineKeyboardMarkup(row_width=1)
    for proxy in proxies:
        from datetime import datetime
        expires = datetime.fromisoformat(proxy["expires_at"].replace("Z", "+00:00")) if isinstance(proxy["expires_at"], str) else proxy["expires_at"]
        days_left = (expires - datetime.now()).days
        status = "🟢" if days_left > 0 else "🔴"
        text = f"{status} {proxy['ip']}:{proxy['port']} ({proxy['country']}) - {days_left} дн."
        kb.add(InlineKeyboardButton(text, callback_data=f"my_proxy:{proxy['id']}"))
    kb.add(InlineKeyboardButton("⬅️ Назад", callback_data="main_menu"))
    return kb


def my_proxy_detail_keyboard(purchase_id: int, proxy_id: int, days_left: int):
    """Individual proxy management."""
    kb = InlineKeyboardMarkup(row_width=2)
    if days_left <= 7:
        kb.add(
            InlineKeyboardButton("➕ Продлить на 7 дней", callback_data=f"extend:{purchase_id}:7"),
            InlineKeyboardButton("➕ Продлить на 30 дней", callback_data=f"extend:{purchase_id}:30"),
        )
    kb.add(
        InlineKeyboardButton("🔄 Вкл/выкл автопродление", callback_data=f"toggle_autorenew:{purchase_id}"),
        InlineKeyboardButton("📋 Скопировать данные", callback_data=f"copy_proxy:{proxy_id}"),
    )
    kb.add(InlineKeyboardButton("⬅️ К списку", callback_data="my_proxies"))
    return kb


def balance_keyboard():
    """Balance management keyboard."""
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("💳 Пополнить баланс", callback_data="deposit:menu"),
        InlineKeyboardButton("📜 История", callback_data="transactions:history"),
    )
    kb.add(InlineKeyboardButton("⬅️ Назад", callback_data="main_menu"))
    return kb


def deposit_amounts_keyboard():
    """Deposit amount selection."""
    kb = InlineKeyboardMarkup(row_width=3)
    amounts = [10, 50, 100, 500, 1000, 5000]
    for i in range(0, len(amounts), 3):
        row = []
        for j in range(3):
            if i + j < len(amounts):
                row.append(InlineKeyboardButton(f"{amounts[i+j]}₽", callback_data=f"deposit:amount:{amounts[i+j]}"))
        kb.add(*row)
    kb.add(InlineKeyboardButton("✏️ Другая сумма", callback_data="deposit:custom"))
    kb.add(InlineKeyboardButton("⬅️ Назад", callback_data="balance"))
    return kb


def referral_keyboard(referral_link: str):
    """Referral program keyboard."""
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton("🔗 Поделиться ссылкой", switch_inline_query=referral_link))
    kb.add(InlineKeyboardButton("📊 Мои рефералы", callback_data="referral:stats"))
    kb.add(InlineKeyboardButton("⬅️ Назад", callback_data="main_menu"))
    return kb


def admin_keyboard():
    """Admin panel keyboard."""
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("➕ Добавить прокси", callback_data="admin:add_proxy"),
        InlineKeyboardButton("📦 Массовый импорт", callback_data="admin:bulk_import"),
    )
    kb.add(
        InlineKeyboardButton("👥 Пользователи", callback_data="admin:users"),
        InlineKeyboardButton("📊 Статистика", callback_data="admin:stats"),
    )
    kb.add(
        InlineKeyboardButton("💰 Выплаты", callback_data="admin:payouts"),
        InlineKeyboardButton("⚙️ Настройки", callback_data="admin:settings"),
    )
    kb.add(InlineKeyboardButton("⬅️ В меню", callback_data="main_menu"))
    return kb


def admin_users_keyboard(users: list, page: int = 0, per_page: int = 10):
    """Admin users list."""
    kb = InlineKeyboardMarkup(row_width=1)
    start = page * per_page
    end = start + per_page
    for user in users[start:end]:
        status = "🚫" if user["is_banned"] else "✅"
        text = f"{status} @{user['username'] or 'N/A'} (ID: {user['user_id']}) - {user['balance']}₽"
        kb.add(InlineKeyboardButton(text, callback_data=f"admin:user:{user['user_id']}"))
    
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("⬅️", callback_data=f"admin:users_page:{page - 1}"))
    if end < len(users):
        nav.append(InlineKeyboardButton("➡️", callback_data=f"admin:users_page:{page + 1}"))
    if nav:
        kb.add(*nav)
    
    kb.add(InlineKeyboardButton("⬅️ Админ панель", callback_data="admin:panel"))
    return kb


def admin_user_keyboard(user_id: int, is_banned: bool):
    """Admin user actions."""
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("🚫 Забанить" if not is_banned else "✅ Разбанить", callback_data=f"admin:toggle_ban:{user_id}"),
        InlineKeyboardButton("💰 Изменить баланс", callback_data=f"admin:change_balance:{user_id}"),
    )
    kb.add(InlineKeyboardButton("📜 История транзакций", callback_data=f"admin:user_transactions:{user_id}"))
    kb.add(InlineKeyboardButton("⬅️ К пользователям", callback_data="admin:users"))
    return kb


def confirm_keyboard(action: str, item_id: int):
    """Confirmation keyboard."""
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("✅ Да", callback_data=f"confirm:{action}:{item_id}"),
        InlineKeyboardButton("❌ Нет", callback_data="cancel"),
    )
    return kb


def cancel_keyboard(callback: str = "main_menu"):
    """Simple cancel keyboard."""
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("❌ Отмена", callback_data=callback))
    return kb