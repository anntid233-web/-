from telebot.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardRemove,
)
from database import ProxyType, OrderStatus
from config import config


# --- Reply Keyboards (main menu) ---

def get_main_menu_keyboard(user_id: int) -> ReplyKeyboardMarkup:
    """Main reply keyboard for users"""
    kb = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    kb.add(
        KeyboardButton("🛒 Купить прокси"),
        KeyboardButton("📦 Мои прокси"),
    )
    kb.add(
        KeyboardButton("👤 Профиль"),
        KeyboardButton("💳 Пополнить баланс"),
    )
    kb.add(
        KeyboardButton("ℹ️ Помощь"),
        KeyboardButton("🎁 Реферальная программа"),
    )

    if user_id in config.ADMIN_IDS:
        kb.add(KeyboardButton("⚙️ Админ-панель"))

    return kb


def get_admin_main_keyboard() -> ReplyKeyboardMarkup:
    """Admin main menu"""
    kb = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    kb.add(
        KeyboardButton("📊 Статистика"),
        KeyboardButton("👥 Пользователи"),
    )
    kb.add(
        KeyboardButton("📦 Прокси"),
        KeyboardButton("📋 Заказы"),
    )
    kb.add(
        KeyboardButton("💰 Финансы"),
        KeyboardButton("📢 Рассылка"),
    )
    kb.add(
        KeyboardButton("⚙️ Настройки"),
        KeyboardButton("🔙 В главное меню"),
    )
    return kb


def get_cancel_keyboard() -> ReplyKeyboardMarkup:
    """Cancel keyboard"""
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(KeyboardButton("❌ Отмена"))
    return kb


# --- Inline Keyboards ---

def get_proxy_types_keyboard() -> InlineKeyboardMarkup:
    """Select proxy type"""
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("🌐 HTTP/HTTPS", callback_data="proxy_type:http"),
        InlineKeyboardButton("🔒 SOCKS5", callback_data="proxy_type:socks5"),
    )
    kb.add(InlineKeyboardButton("❌ Отмена", callback_data="cancel"))
    return kb


def get_countries_keyboard(countries: dict, proxy_type: str, page: int = 0, per_page: int = 10) -> InlineKeyboardMarkup:
    """Select country with pagination"""
    kb = InlineKeyboardMarkup(row_width=2)

    items = list(countries.items())
    start = page * per_page
    end = start + per_page
    page_items = items[start:end]

    for code, name in page_items:
        kb.add(InlineKeyboardButton(
            f"🇺🇳 {name} ({code.upper()})",
            callback_data=f"country:{proxy_type}:{code}"
        ))

    # Pagination
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton("⬅️ Назад", callback_data=f"countries_page:{proxy_type}:{page-1}"))
    if end < len(items):
        nav_buttons.append(InlineKeyboardButton("Вперед ➡️", callback_data=f"countries_page:{proxy_type}:{page+1}"))
    if nav_buttons:
        kb.row(*nav_buttons)

    kb.add(InlineKeyboardButton("❌ Отмена", callback_data="cancel"))
    return kb


def get_count_keyboard(proxy_type: str, country: str) -> InlineKeyboardMarkup:
    """Select proxy count"""
    kb = InlineKeyboardMarkup(row_width=3)
    counts = [1, 2, 3, 5, 10, 20, 50]
    buttons = [
        InlineKeyboardButton(str(c), callback_data=f"count:{proxy_type}:{country}:{c}")
        for c in counts
    ]
    kb.add(*buttons)
    kb.add(InlineKeyboardButton("❌ Отмена", callback_data="cancel"))
    return kb


def get_period_keyboard(proxy_type: str, country: str, count: int) -> InlineKeyboardMarkup:
    """Select rental period"""
    kb = InlineKeyboardMarkup(row_width=2)
    periods = [
        (7, "7 дней"),
        (30, "30 дней"),
        (60, "60 дней"),
        (90, "90 дней"),
    ]
    for days, label in periods:
        kb.add(InlineKeyboardButton(
            label,
            callback_data=f"period:{proxy_type}:{country}:{count}:{days}"
        ))
    kb.add(InlineKeyboardButton("❌ Отмена", callback_data="cancel"))
    return kb


def get_payment_keyboard(payment_url: str, order_id: int) -> InlineKeyboardMarkup:
    """Payment keyboard with link"""
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("💳 Оплатить", url=payment_url))
    kb.add(InlineKeyboardButton("✅ Проверить оплату", callback_data=f"check_payment:{order_id}"))
    kb.add(InlineKeyboardButton("❌ Отменить заказ", callback_data=f"cancel_order:{order_id}"))
    return kb


def get_profile_keyboard() -> InlineKeyboardMarkup:
    """Profile inline keyboard"""
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("💳 Пополнить баланс", callback_data="deposit"),
        InlineKeyboardButton("📋 История заказов", callback_data="my_orders"),
    )
    kb.add(
        InlineKeyboardButton("🎁 Реферальная ссылка", callback_data="referral"),
        InlineKeyboardButton("🔑 Сменить реф. код", callback_data="change_ref_code"),
    )
    return kb


def get_deposit_amounts_keyboard() -> InlineKeyboardMarkup:
    """Quick deposit amounts"""
    kb = InlineKeyboardMarkup(row_width=3)
    amounts = [100, 200, 500, 1000, 2000, 5000]
    buttons = [
        InlineKeyboardButton(f"{a} ₽", callback_data=f"deposit_amount:{a}")
        for a in amounts
    ]
    kb.add(*buttons)
    kb.add(InlineKeyboardButton("💰 Своя сумма", callback_data="deposit_custom"))
    kb.add(InlineKeyboardButton("❌ Отмена", callback_data="cancel"))
    return kb


def get_my_proxies_keyboard(proxies: list, page: int = 0, per_page: int = 5) -> InlineKeyboardMarkup:
    """User's proxies list with pagination"""
    kb = InlineKeyboardMarkup(row_width=1)

    start = page * per_page
    end = start + per_page
    page_proxies = proxies[start:end]

    for proxy in page_proxies:
        status_emoji = "✅" if proxy.status.value == "sold" else "⏳"
        kb.add(InlineKeyboardButton(
            f"{status_emoji} {proxy.ip}:{proxy.port} ({proxy.type.value.upper()}) - {proxy.country or 'N/A'}",
            callback_data=f"proxy_info:{proxy.id}"
        ))

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("⬅️", callback_data=f"my_proxies_page:{page-1}"))
    if end < len(proxies):
        nav.append(InlineKeyboardButton("➡️", callback_data=f"my_proxies_page:{page+1}"))
    if nav:
        kb.row(*nav)

    kb.add(InlineKeyboardButton("🔄 Обновить", callback_data="my_proxies"))
    kb.add(InlineKeyboardButton("❌ Закрыть", callback_data="cancel"))
    return kb


def get_proxy_info_keyboard(proxy_id: int) -> InlineKeyboardMarkup:
    """Single proxy actions"""
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("📋 Копировать", callback_data=f"copy_proxy:{proxy_id}"),
        InlineKeyboardButton("🔄 Продлить", callback_data=f"renew_proxy:{proxy_id}"),
    )
    kb.add(
        InlineKeyboardButton("❌ Удалить", callback_data=f"delete_proxy:{proxy_id}"),
        InlineKeyboardButton("🔙 Назад", callback_data="my_proxies"),
    )
    return kb


# --- Admin Keyboards ---

def get_admin_users_keyboard(page: int = 0, per_page: int = 10) -> InlineKeyboardMarkup:
    """Admin users list"""
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(
        InlineKeyboardButton("🔍 Поиск пользователя", callback_data="admin_search_user"),
        InlineKeyboardButton("📊 Топ по балансу", callback_data="admin_top_balance"),
        InlineKeyboardButton("📊 Топ по заказам", callback_data="admin_top_orders"),
    )
    kb.add(InlineKeyboardButton("🔙 Назад", callback_data="admin_main"))
    return kb


def get_admin_proxies_keyboard() -> InlineKeyboardMarkup:
    """Admin proxy management"""
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("📦 Все прокси", callback_data="admin_all_proxies"),
        InlineKeyboardButton("✅ Доступные", callback_data="admin_available_proxies"),
    )
    kb.add(
        InlineKeyboardButton("🛒 Проданные", callback_data="admin_sold_proxies"),
        InlineKeyboardButton("⏳ Ожидающие", callback_data="admin_pending_proxies"),
    )
    kb.add(
        InlineKeyboardButton("➕ Добавить вручную", callback_data="admin_add_proxy"),
        InlineKeyboardButton("🔄 Синхронизировать с API", callback_data="admin_sync_proxies"),
    )
    kb.add(InlineKeyboardButton("🔙 Назад", callback_data="admin_main"))
    return kb


def get_admin_orders_keyboard() -> InlineKeyboardMarkup:
    """Admin orders management"""
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("⏳ Ожидающие оплаты", callback_data="admin_orders:pending"),
        InlineKeyboardButton("✅ Оплаченные", callback_data="admin_orders:paid"),
    )
    kb.add(
        InlineKeyboardButton("📦 Выполненные", callback_data="admin_orders:completed"),
        InlineKeyboardButton("❌ Отмененные", callback_data="admin_orders:failed"),
    )
    kb.add(InlineKeyboardButton("🔙 Назад", callback_data="admin_main"))
    return kb


def get_admin_finance_keyboard() -> InlineKeyboardMarkup:
    """Admin finance"""
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("💰 Баланс бота", callback_data="admin_bot_balance"),
        InlineKeyboardButton("📥 Пополнения", callback_data="admin_deposits"),
    )
    kb.add(
        InlineKeyboardButton("📤 Выводы", callback_data="admin_withdrawals"),
        InlineKeyboardButton("📊 Отчет за день", callback_data="admin_report_day"),
    )
    kb.add(
        InlineKeyboardButton("📊 Отчет за неделю", callback_data="admin_report_week"),
        InlineKeyboardButton("📊 Отчет за месяц", callback_data="admin_report_month"),
    )
    kb.add(InlineKeyboardButton("🔙 Назад", callback_data="admin_main"))
    return kb


def get_admin_settings_keyboard() -> InlineKeyboardMarkup:
    """Admin settings"""
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(
        InlineKeyboardButton("💲 Минимальное пополнение", callback_data="admin_set_min_deposit"),
        InlineKeyboardButton("🎁 Реферальный бонус", callback_data="admin_set_ref_bonus"),
    )
    kb.add(
        InlineKeyboardButton("📈 Наценка на прокси", callback_data="admin_set_markup"),
        InlineKeyboardButton("🌐 Страны по умолчанию", callback_data="admin_default_countries"),
    )
    kb.add(
        InlineKeyboardButton("🔧 Тех. работы", callback_data="admin_maintenance"),
        InlineKeyboardButton("🔙 Назад", callback_data="admin_main"),
    )
    return kb


def get_broadcast_confirm_keyboard() -> InlineKeyboardMarkup:
    """Broadcast confirmation"""
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("✅ Отправить", callback_data="broadcast_confirm"),
        InlineKeyboardButton("❌ Отмена", callback_data="broadcast_cancel"),
    )
    return kb


def get_order_actions_keyboard(order_id: int, status: OrderStatus) -> InlineKeyboardMarkup:
    """Admin order actions"""
    kb = InlineKeyboardMarkup(row_width=2)

    if status == OrderStatus.PENDING:
        kb.add(
            InlineKeyboardButton("✅ Подтвердить оплату", callback_data=f"admin_confirm_order:{order_id}"),
            InlineKeyboardButton("❌ Отменить", callback_data=f"admin_cancel_order:{order_id}"),
        )
    elif status == OrderStatus.PAID:
        kb.add(
            InlineKeyboardButton("📦 Выдать прокси", callback_data=f"admin_fulfill_order:{order_id}"),
            InlineKeyboardButton("💰 Вернуть деньги", callback_data=f"admin_refund_order:{order_id}"),
        )

    kb.add(
        InlineKeyboardButton("👤 Пользователь", callback_data=f"admin_view_user_from_order:{order_id}"),
        InlineKeyboardButton("🔙 Назад", callback_data="admin_orders"),
    )
    return kb


def get_user_actions_keyboard(user_id: int) -> InlineKeyboardMarkup:
    """Admin user actions"""
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("💰 Изменить баланс", callback_data=f"admin_change_balance:{user_id}"),
        InlineKeyboardButton("🚫 Бан/Разбан", callback_data=f"admin_toggle_ban:{user_id}"),
    )
    kb.add(
        InlineKeyboardButton("📋 Заказы пользователя", callback_data=f"admin_user_orders:{user_id}"),
        InlineKeyboardButton("📦 Прокси пользователя", callback_data=f"admin_user_proxies:{user_id}"),
    )
    kb.add(
        InlineKeyboardButton("💬 Написать пользователю", callback_data=f"admin_message_user:{user_id}"),
        InlineKeyboardButton("🔙 Назад", callback_data="admin_users"),
    )
    return kb


def get_proxy_actions_keyboard(proxy_id: int) -> InlineKeyboardMarkup:
    """Admin proxy actions"""
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("🔄 Продлить", callback_data=f"admin_renew_proxy:{proxy_id}"),
        InlineKeyboardButton("🔄 Сменить IP", callback_data=f"admin_change_ip:{proxy_id}"),
    )
    kb.add(
        InlineKeyboardButton("❌ Удалить", callback_data=f"admin_delete_proxy:{proxy_id}"),
        InlineKeyboardButton("🔙 Назад", callback_data="admin_proxies"),
    )
    return kb


def get_pagination_keyboard(current_page: int, total_pages: int, prefix: str) -> InlineKeyboardMarkup:
    """Generic pagination keyboard"""
    kb = InlineKeyboardMarkup(row_width=5)

    buttons = []
    if current_page > 0:
        buttons.append(InlineKeyboardButton("⬅️", callback_data=f"{prefix}_page:{current_page-1}"))

    # Page numbers
    start = max(0, current_page - 2)
    end = min(total_pages, current_page + 3)
    for i in range(start, end):
        text = f"• {i+1} •" if i == current_page else str(i+1)
        buttons.append(InlineKeyboardButton(text, callback_data=f"{prefix}_page:{i}"))

    if current_page < total_pages - 1:
        buttons.append(InlineKeyboardButton("➡️", callback_data=f"{prefix}_page:{current_page+1}"))

    kb.add(*buttons)
    kb.add(InlineKeyboardButton("🔙 Назад", callback_data=f"{prefix}_back"))
    return kb


# Utility

def get_reply_keyboard_remove() -> ReplyKeyboardRemove:
    return ReplyKeyboardRemove()