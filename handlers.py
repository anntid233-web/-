import telebot
from telebot.types import Message, CallbackQuery, InlineQuery, InlineQueryResultArticle, InputTextMessageContent
from config import config
from database import (
    get_or_create_user, get_user, update_balance, get_user_by_referral_code,
    get_available_proxies, get_proxy, reserve_proxy, sell_proxy, release_proxy,
    get_user_proxies, create_purchase, get_purchase, extend_purchase,
    create_transaction, complete_transaction, get_user_transactions,
    get_setting, set_setting, get_stats, add_proxy
)
from keyboards import (
    main_menu_keyboard, catalog_keyboard, countries_keyboard, types_keyboard,
    proxy_list_keyboard, proxy_detail_keyboard, payment_keyboard,
    my_proxies_keyboard, my_proxy_detail_keyboard, balance_keyboard,
    deposit_amounts_keyboard, referral_keyboard, admin_keyboard,
    admin_users_keyboard, admin_user_keyboard, confirm_keyboard, cancel_keyboard
)
from payments import process_deposit, handle_successful_payment, get_payment_provider
import re
from datetime import datetime, timedelta


bot = telebot.TeleBot(config.BOT_TOKEN, parse_mode="HTML")

# User states for multi-step operations
user_states = {}


def is_admin(user_id: int) -> bool:
    return user_id in config.ADMIN_IDS


# ==================== Main Handlers ====================

@bot.message_handler(commands=["start"])
async def start_handler(message: Message):
    """Handle /start command with optional referral."""
    args = message.text.split()
    referred_by = None
    
    if len(args) > 1 and args[1].startswith("ref_"):
        ref_code = args[1][4:]
        referrer = await get_user_by_referral_code(ref_code)
        if referrer and referrer["user_id"] != message.from_user.id:
            referred_by = referrer["user_id"]
    
    user = await get_or_create_user(
        message.from_user.id,
        message.from_user.username,
        message.from_user.first_name,
        message.from_user.last_name,
        referred_by
    )
    
    welcome_msg = await get_setting("welcome_message")
    if not welcome_msg:
        welcome_msg = "👋 Добро пожаловать в Proxy Shop Bot!\n\nЗдесь вы можете купить качественные прокси для любых задач."
    
    await bot.send_message(
        message.chat.id,
        welcome_msg,
        reply_markup=main_menu_keyboard(message.from_user.id)
    )


@bot.message_handler(commands=["menu"])
async def menu_handler(message: Message):
    """Show main menu."""
    await bot.send_message(
        message.chat.id,
        "🏠 Главное меню:",
        reply_markup=main_menu_keyboard(message.from_user.id)
    )


@bot.message_handler(func=lambda m: m.text == "🛒 Каталог прокси")
async def catalog_handler(message: Message):
    """Show proxy catalog."""
    await bot.send_message(
        message.chat.id,
        "🛒 <b>Каталог прокси</b>\n\nВыберите способ поиска:",
        reply_markup=catalog_keyboard()
    )


@bot.message_handler(func=lambda m: m.text == "💼 Мои прокси")
async def my_proxies_handler(message: Message):
    """Show user's purchased proxies."""
    proxies = await get_user_proxies(message.from_user.id)
    
    if not proxies:
        await bot.send_message(
            message.chat.id,
            "📭 У вас нет активных прокси.\n\nПерейдите в каталог, чтобы приобрести!",
            reply_markup=main_menu_keyboard(message.from_user.id)
        )
        return
    
    await bot.send_message(
        message.chat.id,
        f"💼 <b>Ваши прокси ({len(proxies)})</b>\n\nВыберите прокси для управления:",
        reply_markup=my_proxies_keyboard(proxies)
    )


@bot.message_handler(func=lambda m: m.text == "💰 Баланс")
async def balance_handler(message: Message):
    """Show user balance."""
    user = await get_user(message.from_user.id)
    balance = user["balance"] if user else 0
    
    await bot.send_message(
        message.chat.id,
        f"💰 <b>Ваш баланс: {balance:.2f}₽</b>\n\nВыберите действие:",
        reply_markup=balance_keyboard()
    )


@bot.message_handler(func=lambda m: m.text == "📊 Статистика")
async def stats_handler(message: Message):
    """Show bot statistics."""
    stats = await get_stats()
    user = await get_user(message.from_user.id)
    
    text = (
        f"📊 <b>Статистика бота</b>\n\n"
        f"👥 Всего пользователей: {stats['total_users']}\n"
        f"🟢 Доступно прокси: {stats['available_proxies']}\n"
        f"🔴 Продано прокси: {stats['sold_proxies']}\n"
        f"💰 Общий оборот: {stats['total_revenue']:.2f}₽\n\n"
        f"👤 <b>Ваша статистика</b>\n"
        f"💵 Баланс: {user['balance']:.2f}₽\n"
        f"💸 Всего потрачено: {user['total_spent']:.2f}₽\n"
        f"📅 Регистрация: {user['created_at'][:10]}"
    )
    
    await bot.send_message(message.chat.id, text, reply_markup=main_menu_keyboard(message.from_user.id))


@bot.message_handler(func=lambda m: m.text == "👥 Реферальная программа")
async def referral_handler(message: Message):
    """Show referral program info."""
    user = await get_user(message.from_user.id)
    bot_info = await bot.get_me()
    referral_link = f"https://t.me/{bot_info.username}?start=ref_{user['referral_code']}"
    
    text = (
        f"👥 <b>Реферальная программа</b>\n\n"
        f"Приглашайте друзей и получайте <b>{config.REFERRAL_BONUS_PERCENT}%</b> от их пополнений!\n\n"
        f"🔗 Ваша реферальная ссылка:\n<code>{referral_link}</code>\n\n"
        f"📋 Реферальный код: <code>{user['referral_code']}</code>"
    )
    
    await bot.send_message(message.chat.id, text, reply_markup=referral_keyboard(referral_link))


@bot.message_handler(func=lambda m: m.text == "ℹ️ Помощь")
async def help_handler(message: Message):
    """Show help message."""
    text = (
        "ℹ️ <b>Помощь</b>\n\n"
        "<b>Как купить прокси:</b>\n"
        "1. Зайдите в «🛒 Каталог прокси»\n"
        "2. Выберите страну или тип прокси\n"
        "3. Выберите понравившийся прокси\n"
        "4. Выберите срок аренды и оплатите\n\n"
        "<b>Типы прокси:</b>\n"
        "• HTTP/HTTPS — для браузинга и парсинга\n"
        "• SOCKS4/SOCKS5 — для программ и ботов\n\n"
        "<b>Оплата:</b>\n"
        "• Баланс бота (пополнение через CryptoBot/ЮMoney)\n"
        "• Автопродление списывает средства за 1 день до окончания\n\n"
        f"📞 Поддержка: {config.SUPPORT_USERNAME}"
    )
    
    await bot.send_message(message.chat.id, text, reply_markup=main_menu_keyboard(message.from_user.id))


@bot.message_handler(func=lambda m: m.text == "⚙️ Админ панель")
async def admin_panel_handler(message: Message):
    """Show admin panel."""
    if not is_admin(message.from_user.id):
        await bot.send_message(message.chat.id, "⛔ Доступ запрещен.")
        return
    
    await bot.send_message(
        message.chat.id,
        "⚙️ <b>Админ панель</b>\n\nВыберите действие:",
        reply_markup=admin_keyboard()
    )


# ==================== Catalog Callbacks ====================

@bot.callback_query_handler(func=lambda c: c.data == "catalog:main")
async def catalog_main_callback(call: CallbackQuery):
    """Back to catalog main."""
    await bot.edit_message_text(
        "🛒 <b>Каталог прокси</b>\n\nВыберите способ поиска:",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=catalog_keyboard()
    )


@bot.callback_query_handler(func=lambda c: c.data == "catalog:countries")
async def catalog_countries_callback(call: CallbackQuery):
    """Show countries list."""
    countries_str = await get_setting("countries")
    countries = countries_str.split(",") if countries_str else []
    
    await bot.edit_message_text(
        "🌍 <b>Выберите страну:</b>",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=countries_keyboard(countries)
    )


@bot.callback_query_handler(func=lambda c: c.data.startswith("countries_page:"))
async def countries_page_callback(call: CallbackQuery):
    """Countries pagination."""
    page = int(call.data.split(":")[1])
    countries_str = await get_setting("countries")
    countries = countries_str.split(",") if countries_str else []
    
    await bot.edit_message_reply_markup(
        call.message.chat.id,
        call.message.message_id,
        reply_markup=countries_keyboard(countries, page)
    )


@bot.callback_query_handler(func=lambda c: c.data.startswith("country:"))
async def country_callback(call: CallbackQuery):
    """Show proxies for selected country."""
    country = call.data.split(":")[1]
    proxies = await get_available_proxies(country=country)
    
    if not proxies:
        await bot.edit_message_text(
            f"😔 В стране {country} пока нет доступных прокси.",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=catalog_keyboard()
        )
        return
    
    await bot.edit_message_text(
        f"🌍 <b>Прокси в {country} ({len(proxies)})</b>\n\nВыберите прокси:",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=proxy_list_keyboard(proxies, country=country)
    )


@bot.callback_query_handler(func=lambda c: c.data == "catalog:types")
async def catalog_types_callback(call: CallbackQuery):
    """Show proxy types."""
    types_str = await get_setting("proxy_types")
    types = types_str.split(",") if types_str else ["http", "https", "socks4", "socks5"]
    
    await bot.edit_message_text(
        "🔧 <b>Выберите тип прокси:</b>",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=types_keyboard(types)
    )


@bot.callback_query_handler(func=lambda c: c.data.startswith("type:"))
async def type_callback(call: CallbackQuery):
    """Show proxies for selected type."""
    proxy_type = call.data.split(":")[1]
    proxies = await get_available_proxies(proxy_type=proxy_type)
    
    if not proxies:
        await bot.edit_message_text(
            f"😔 Прокси типа {proxy_type.upper()} пока недоступны.",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=catalog_keyboard()
        )
        return
    
    await bot.edit_message_text(
        f"🔧 <b>Прокси {proxy_type.upper()} ({len(proxies)})</b>\n\nВыберите прокси:",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=proxy_list_keyboard(proxies, proxy_type=proxy_type)
    )


@bot.callback_query_handler(func=lambda c: c.data.startswith("list_page:"))
async def list_page_callback(call: CallbackQuery):
    """Proxy list pagination."""
    _, page, country, proxy_type = call.data.split(":")
    page = int(page)
    country = None if country == "all" else country
    proxy_type = None if proxy_type == "all" else proxy_type
    
    proxies = await get_available_proxies(country=country, proxy_type=proxy_type)
    
    await bot.edit_message_reply_markup(
        call.message.chat.id,
        call.message.message_id,
        reply_markup=proxy_list_keyboard(proxies, country, proxy_type, page)
    )


@bot.callback_query_handler(func=lambda c: c.data.startswith("proxy:"))
async def proxy_detail_callback(call: CallbackQuery):
    """Show proxy details with purchase options."""
    proxy_id = int(call.data.split(":")[1])
    proxy = await get_proxy(proxy_id)
    
    if not proxy or proxy["status"] != "available":
        await bot.answer_callback_query(call.id, "❌ Прокси недоступен", show_alert=True)
        return
    
    user = await get_user(call.from_user.id)
    balance = user["balance"] if user else 0
    
    auth_info = ""
    if proxy["username"] and proxy["password"]:
        auth_info = f"\n🔐 Логин: <code>{proxy['username']}</code>\n🔑 Пароль: <code>{proxy['password']}</code>"
    
    text = (
        f"🔍 <b>Детали прокси #{proxy_id}</b>\n\n"
        f"🌐 IP: <code>{proxy['ip']}:{proxy['port']}</code>\n"
        f"🌍 Страна: {proxy['country']}\n"
        f"🏙 Город: {proxy['city'] or 'Не указан'}\n"
        f"🏢 Провайдер: {proxy['isp'] or 'Не указан'}\n"
        f"🔧 Тип: {proxy['type'].upper()}{auth_info}\n\n"
        f"💰 <b>Цены:</b>\n"
    )
    
    if proxy["price_per_day"]:
        text += f"• 1 день: {proxy['price_per_day']}₽\n"
    if proxy["price_per_week"]:
        text += f"• 7 дней: {proxy['price_per_week']}₽\n"
    if proxy["price_per_month"]:
        text += f"• 30 дней: {proxy['price_per_month']}₽\n"
    
    text += f"\n💵 Ваш баланс: {balance:.2f}₽"
    
    await bot.edit_message_text(
        text,
        call.message.chat.id,
        call.message.message_id,
        reply_markup=proxy_detail_keyboard(proxy_id, balance)
    )


# ==================== Purchase Flow ====================

@bot.callback_query_handler(func=lambda c: c.data.startswith("buy:"))
async def buy_proxy_callback(call: CallbackQuery):
    """Initiate proxy purchase."""
    _, proxy_id, days = call.data.split(":")
    proxy_id = int(proxy_id)
    days = int(days)
    
    proxy = await get_proxy(proxy_id)
    if not proxy or proxy["status"] != "available":
        await bot.answer_callback_query(call.id, "❌ Прокси недоступен", show_alert=True)
        return
    
    # Get price for selected duration
    price_map = {1: "price_per_day", 7: "price_per_week", 30: "price_per_month"}
    price_field = price_map.get(days)
    price = proxy[price_field] if price_field else 0
    
    if price <= 0:
        await bot.answer_callback_query(call.id, "❌ Цена не установлена для этого срока", show_alert=True)
        return
    
    user = await get_user(call.from_user.id)
    if user["balance"] < price:
        # Need to deposit
        await bot.edit_message_text(
            f"💰 <b>Недостаточно средств</b>\n\n"
            f"Цена: {price}₽\n"
            f"Ваш баланс: {user['balance']:.2f}₽\n\n"
            f"Пополните баланс для покупки:",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=balance_keyboard()
        )
        return
    
    # Reserve proxy
    reserved = await reserve_proxy(proxy_id, call.from_user.id)
    if not reserved:
        await bot.answer_callback_query(call.id, "❌ Прокси уже занят", show_alert=True)
        return
    
    # Deduct balance and create purchase
    await update_balance(call.from_user.id, -price)
    purchase_id = await create_purchase(call.from_user.id, proxy_id, days, price)
    await sell_proxy(proxy_id)
    
    # Record transaction
    await create_transaction(call.from_user.id, -price, "purchase", "balance", str(purchase_id),
                           f"Покупка прокси {proxy['ip']}:{proxy['port']} на {days} дн.")
    
    # Send proxy details
    auth_text = ""
    if proxy["username"] and proxy["password"]:
        auth_text = f"\n🔐 Логин: <code>{proxy['username']}</code>\n🔑 Пароль: <code>{proxy['password']}</code>"
    
    expires = datetime.now() + timedelta(days=days)
    
    await bot.edit_message_text(
        f"✅ <b>Покупка успешна!</b>\n\n"
        f"🔍 Прокси: <code>{proxy['ip']}:{proxy['port']}</code>{auth_text}\n"
        f"🌍 Страна: {proxy['country']}\n"
        f"🔧 Тип: {proxy['type'].upper()}\n"
        f"📅 Срок: до {expires.strftime('%d.%m.%Y %H:%M')}\n"
        f"💰 Списано: {price}₽\n"
        f"💵 Остаток: {user['balance'] - price:.2f}₽",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=my_proxy_detail_keyboard(purchase_id, proxy_id, days)
    )


# ==================== My Proxies Management ====================

@bot.callback_query_handler(func=lambda c: c.data == "my_proxies")
async def my_proxies_callback(call: CallbackQuery):
    """Show user's proxies."""
    proxies = await get_user_proxies(call.from_user.id)
    
    if not proxies:
        await bot.edit_message_text(
            "📭 У вас нет активных прокси.",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=main_menu_keyboard(call.from_user.id)
        )
        return
    
    await bot.edit_message_text(
        f"💼 <b>Ваши прокси ({len(proxies)})</b>",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=my_proxies_keyboard(proxies)
    )


@bot.callback_query_handler(func=lambda c: c.data.startswith("my_proxy:"))
async def my_proxy_detail_callback(call: CallbackQuery):
    """Show individual proxy details."""
    proxy_id = int(call.data.split(":")[1])
    
    # Find purchase for this proxy
    from database import get_db
    async with get_db() as db:
        cursor = await db.execute(
            """SELECT pur.*, p.* FROM purchases pur
               JOIN proxies p ON pur.proxy_id = p.id
               WHERE pur.user_id = ? AND pur.proxy_id = ? AND pur.status = 'active'
               ORDER BY pur.expires_at DESC LIMIT 1""",
            (call.from_user.id, proxy_id)
        )
        purchase = await cursor.fetchone()
    
    if not purchase:
        await bot.answer_callback_query(call.id, "❌ Прокси не найден", show_alert=True)
        return
    
    expires = datetime.fromisoformat(purchase["expires_at"].replace("Z", "+00:00"))
    days_left = (expires - datetime.now()).days
    
    auth_text = ""
    if purchase["username"] and purchase["password"]:
        auth_text = f"\n🔐 Логин: <code>{purchase['username']}</code>\n🔑 Пароль: <code>{purchase['password']}</code>"
    
    auto_renew = "🟢 Включено" if purchase["auto_renew"] else "🔴 Выключено"
    
    text = (
        f"🔍 <b>Прокси #{proxy_id}</b>\n\n"
        f"🌐 IP: <code>{purchase['ip']}:{purchase['port']}</code>{auth_text}\n"
        f"🌍 Страна: {purchase['country']}\n"
        f"🔧 Тип: {purchase['type'].upper()}\n"
        f"📅 Осталось: {days_left} дн.\n"
        f"🔄 Автопродление: {auto_renew}"
    )
    
    await bot.edit_message_text(
        text,
        call.message.chat.id,
        call.message.message_id,
        reply_markup=my_proxy_detail_keyboard(purchase["id"], proxy_id, days_left)
    )


@bot.callback_query_handler(func=lambda c: c.data.startswith("extend:"))
async def extend_proxy_callback(call: CallbackQuery):
    """Extend proxy rental."""
    _, purchase_id, days = call.data.split(":")
    purchase_id = int(purchase_id)
    days = int(days)
    
    purchase = await get_purchase(purchase_id)
    if not purchase or purchase["user_id"] != call.from_user.id:
        await bot.answer_callback_query(call.id, "❌ Покупка не найдена", show_alert=True)
        return
    
    proxy = await get_proxy(purchase["proxy_id"])
    price_field = {7: "price_per_week", 30: "price_per_month"}.get(days)
    price = proxy[price_field] if price_field and proxy else 0
    
    if price <= 0:
        await bot.answer_callback_query(call.id, "❌ Цена не установлена", show_alert=True)
        return
    
    user = await get_user(call.from_user.id)
    if user["balance"] < price:
        await bot.answer_callback_query(call.id, f"❌ Недостаточно средств. Нужно: {price}₽", show_alert=True)
        return
    
    await update_balance(call.from_user.id, -price)
    await extend_purchase(purchase_id, days)
    
    await create_transaction(call.from_user.id, -price, "purchase", "balance", str(purchase_id),
                           f"Продление прокси на {days} дн.")
    
    await bot.answer_callback_query(call.id, f"✅ Прокси продлен на {days} дней!")
    
    # Refresh
    await my_proxy_detail_callback(call)


@bot.callback_query_handler(func=lambda c: c.data.startswith("toggle_autorenew:"))
async def toggle_autorenew_callback(call: CallbackQuery):
    """Toggle auto-renewal."""
    purchase_id = int(call.data.split(":")[1])
    
    purchase = await get_purchase(purchase_id)
    if not purchase or purchase["user_id"] != call.from_user.id:
        await bot.answer_callback_query(call.id, "❌ Покупка не найдена", show_alert=True)
        return
    
    new_value = 0 if purchase["auto_renew"] else 1
    
    from database import get_db
    async with get_db() as db:
        await db.execute(
            "UPDATE purchases SET auto_renew = ? WHERE id = ?",
            (new_value, purchase_id)
        )
        await db.commit()
    
    status = "включено" if new_value else "выключено"
    await bot.answer_callback_query(call.id, f"✅ Автопродление {status}!")
    
    # Refresh
    await my_proxy_detail_callback(call)


@bot.callback_query_handler(func=lambda c: c.data.startswith("copy_proxy:"))
async def copy_proxy_callback(call: CallbackQuery):
    """Copy proxy credentials to clipboard (show in message)."""
    proxy_id = int(call.data.split(":")[1])
    proxy = await get_proxy(proxy_id)
    
    if not proxy:
        await bot.answer_callback_query(call.id, "❌ Прокси не найден", show_alert=True)
        return
    
    formats = []
    if proxy["username"] and proxy["password"]:
        formats.append(f"{proxy['type']}://{proxy['username']}:{proxy['password']}@{proxy['ip']}:{proxy['port']}")
    else:
        formats.append(f"{proxy['type']}://{proxy['ip']}:{proxy['port']}")
    
    text = "📋 <b>Данные для подключения:</b>\n\n"
    for fmt in formats:
        text += f"<code>{fmt}</code>\n\n"
    text += "Нажмите на код, чтобы скопировать."
    
    await bot.send_message(call.message.chat.id, text)


# ==================== Balance & Payments ====================

@bot.callback_query_handler(func=lambda c: c.data == "balance")
async def balance_callback(call: CallbackQuery):
    """Show balance menu."""
    user = await get_user(call.from_user.id)
    balance = user["balance"] if user else 0
    
    await bot.edit_message_text(
        f"💰 <b>Ваш баланс: {balance:.2f}₽</b>\n\nВыберите действие:",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=balance_keyboard()
    )


@bot.callback_query_handler(func=lambda c: c.data == "deposit:menu")
async def deposit_menu_callback(call: CallbackQuery):
    """Show deposit amount selection."""
    await bot.edit_message_text(
        "💳 <b>Пополнение баланса</b>\n\nВыберите сумму или введите свою:",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=deposit_amounts_keyboard()
    )


@bot.callback_query_handler(func=lambda c: c.data.startswith("deposit:amount:"))
async def deposit_amount_callback(call: CallbackQuery):
    """Process deposit with selected amount."""
    amount = float(call.data.split(":")[2])
    user_id = call.from_user.id
    
    try:
        payment = await process_deposit(user_id, amount)
        
        await bot.edit_message_text(
            f"💳 <b>Пополнение на {amount} {'USDT' if config.PAYMENT_PROVIDER == 'cryptobot' else 'RUB'}</b>\n\n"
            f"Перейдите по ссылке для оплаты:",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=payment_keyboard(amount, payment["payment_id"], config.PAYMENT_PROVIDER)
        )
    except Exception as e:
        await bot.answer_callback_query(call.id, f"❌ Ошибка: {str(e)}", show_alert=True)


@bot.callback_query_handler(func=lambda c: c.data == "deposit:custom")
async def deposit_custom_callback(call: CallbackQuery):
    """Ask for custom deposit amount."""
    user_states[call.from_user.id] = {"state": "waiting_deposit_amount"}
    
    await bot.edit_message_text(
        "✏️ <b>Введите сумму пополнения (минимум {:.2f}₽):</b>".format(config.MIN_DEPOSIT),
        call.message.chat.id,
        call.message.message_id,
        reply_markup=cancel_keyboard("deposit:menu")
    )


@bot.callback_query_handler(func=lambda c: c.data.startswith("check_payment:"))
async def check_payment_callback(call: CallbackQuery):
    """Check payment status."""
    payment_id = call.data.split(":")[1]
    
    success, amount = await handle_successful_payment(call.from_user.id, payment_id, config.PAYMENT_PROVIDER)
    
    if success:
        await bot.edit_message_text(
            f"✅ <b>Оплата подтверждена!</b>\n\n"
            f"💰 Начислено: {amount:.2f}₽\n"
            f"Баланс обновлен.",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=balance_keyboard()
        )
    else:
        await bot.answer_callback_query(call.id, "⏳ Платеж не найден или еще не обработан. Попробуйте позже.", show_alert=True)


@bot.callback_query_handler(func=lambda c: c.data == "transactions:history")
async def transactions_history_callback(call: CallbackQuery):
    """Show transaction history."""
    transactions = await get_user_transactions(call.from_user.id)
    
    if not transactions:
        await bot.edit_message_text(
            "📜 История транзакций пуста.",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=balance_keyboard()
        )
        return
    
    text = "📜 <b>История транзакций (последние 20)</b>\n\n"
    for t in transactions:
        status_emoji = {"completed": "✅", "pending": "⏳", "failed": "❌", "cancelled": "🚫"}.get(t["status"], "❓")
        type_emoji = {"deposit": "💳", "purchase": "🛒", "refund": "🔙", "referral_bonus": "👥", "withdrawal": "💸"}.get(t["type"], "📝")
        sign = "+" if t["type"] in ["deposit", "referral_bonus"] else "-"
        
        text += f"{status_emoji} {type_emoji} {sign}{t['amount']:.2f}₽ — {t['description'] or t['type']}\n"
        text += f"   📅 {t['created_at'][:16]}\n\n"
    
    await bot.edit_message_text(
        text,
        call.message.chat.id,
        call.message.message_id,
        reply_markup=balance_keyboard()
    )


# ==================== Referral ====================

@bot.callback_query_handler(func=lambda c: c.data == "referral:stats")
async def referral_stats_callback(call: CallbackQuery):
    """Show referral statistics."""
    from database import get_db
    async with get_db() as db:
        cursor = await db.execute(
            """SELECT u.user_id, u.username, u.first_name, u.created_at,
                      COUNT(t.id) as deposits, SUM(t.amount) as total_deposited
               FROM users u
               LEFT JOIN transactions t ON u.user_id = t.user_id AND t.type = 'deposit' AND t.status = 'completed'
               WHERE u.referred_by = ?
               GROUP BY u.user_id""",
            (call.from_user.id,)
        )
        referrals = await cursor.fetchall()
    
    text = f"👥 <b>Ваши рефералы ({len(referrals)})</b>\n\n"
    total_bonus = 0
    
    for ref in referrals:
        bonus = (ref["total_deposited"] or 0) * (config.REFERRAL_BONUS_PERCENT / 100)
        total_bonus += bonus
        name = f"@{ref['username']}" if ref["username"] else ref["first_name"] or "Без имени"
        text += f"• {name} — {ref['deposits']} пополн., {ref['total_deposited'] or 0:.2f}₽ (бонус: {bonus:.2f}₽)\n"
    
    text += f"\n💰 <b>Всего заработано: {total_bonus:.2f}₽</b>"
    
    await bot.edit_message_text(
        text,
        call.message.chat.id,
        call.message.message_id,
        reply_markup=referral_keyboard("")
    )


# ==================== Admin Panel ====================

@bot.callback_query_handler(func=lambda c: c.data == "admin:panel")
async def admin_panel_callback(call: CallbackQuery):
    """Show admin panel."""
    if not is_admin(call.from_user.id):
        await bot.answer_callback_query(call.id, "⛔ Доступ запрещен", show_alert=True)
        return
    
    await bot.edit_message_text(
        "⚙️ <b>Админ панель</b>",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=admin_keyboard()
    )


@bot.callback_query_handler(func=lambda c: c.data == "admin:stats")
async def admin_stats_callback(call: CallbackQuery):
    """Show detailed stats."""
    if not is_admin(call.from_user.id):
        return
    
    stats = await get_stats()
    
    from database import get_db
    async with get_db() as db:
        cursor = await db.execute("SELECT COUNT(*) as cnt FROM purchases WHERE status = 'active'")
        active_purchases = (await cursor.fetchone())["cnt"]
        cursor = await db.execute("SELECT SUM(amount) as total FROM transactions WHERE type = 'deposit' AND status = 'completed' AND created_at > datetime('now', '-7 days')")
        week_revenue = (await cursor.fetchone())["total"] or 0
        cursor = await db.execute("SELECT SUM(amount) as total FROM transactions WHERE type = 'deposit' AND status = 'completed' AND created_at > datetime('now', '-30 days')")
        month_revenue = (await cursor.fetchone())["total"] or 0
    
    text = (
        f"📊 <b>Подробная статистика</b>\n\n"
        f"👥 Пользователей: {stats['total_users']}\n"
        f"🟢 Прокси в наличии: {stats['available_proxies']}\n"
        f"🔴 Продано: {stats['sold_proxies']}\n"
        f"📦 Активных аренд: {active_purchases}\n\n"
        f"💰 Выручка за неделю: {week_revenue:.2f}₽\n"
        f"💰 Выручка за месяц: {month_revenue:.2f}₽\n"
        f"💰 Всего: {stats['total_revenue']:.2f}₽"
    )
    
    await bot.edit_message_text(
        text,
        call.message.chat.id,
        call.message.message_id,
        reply_markup=admin_keyboard()
    )


@bot.callback_query_handler(func=lambda c: c.data == "admin:users")
async def admin_users_callback(call: CallbackQuery):
    """Show users list."""
    if not is_admin(call.from_user.id):
        return
    
    from database import get_db
    async with get_db() as db:
        cursor = await db.execute("SELECT * FROM users ORDER BY created_at DESC LIMIT 50")
        users = await cursor.fetchall()
    
    await bot.edit_message_text(
        "👥 <b>Пользователи (последние 50)</b>",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=admin_users_keyboard(users)
    )


@bot.callback_query_handler(func=lambda c: c.data.startswith("admin:users_page:"))
async def admin_users_page_callback(call: CallbackQuery):
    """Users pagination."""
    if not is_admin(call.from_user.id):
        return
    
    page = int(call.data.split(":")[2])
    from database import get_db
    async with get_db() as db:
        cursor = await db.execute("SELECT * FROM users ORDER BY created_at DESC")
        users = await cursor.fetchall()
    
    await bot.edit_message_reply_markup(
        call.message.chat.id,
        call.message.message_id,
        reply_markup=admin_users_keyboard(users, page)
    )


@bot.callback_query_handler(func=lambda c: c.data.startswith("admin:user:"))
async def admin_user_callback(call: CallbackQuery):
    """Show user details."""
    if not is_admin(call.from_user.id):
        return
    
    user_id = int(call.data.split(":")[2])
    user = await get_user(user_id)
    
    if not user:
        await bot.answer_callback_query(call.id, "❌ Пользователь не найден", show_alert=True)
        return
    
    text = (
        f"👤 <b>Пользователь #{user_id}</b>\n\n"
        f"👤 Имя: {user['first_name'] or ''} {user['last_name'] or ''}\n"
        f"🔗 Username: @{user['username'] or 'Нет'}\n"
        f"💰 Баланс: {user['balance']:.2f}₽\n"
        f"💸 Потрачено: {user['total_spent']:.2f}₽\n"
        f"👥 Рефералов: {len(await get_user_by_referral_code(user['referral_code']) or [])}\n"
        f"📅 Регистрация: {user['created_at']}\n"
        f"🚫 Забанен: {'Да' if user['is_banned'] else 'Нет'}"
    )
    
    await bot.edit_message_text(
        text,
        call.message.chat.id,
        call.message.message_id,
        reply_markup=admin_user_keyboard(user_id, user["is_banned"])
    )


@bot.callback_query_handler(func=lambda c: c.data.startswith("admin:toggle_ban:"))
async def admin_toggle_ban_callback(call: CallbackQuery):
    """Ban/unban user."""
    if not is_admin(call.from_user.id):
        return
    
    user_id = int(call.data.split(":")[2])
    
    from database import get_db
    async with get_db() as db:
        cursor = await db.execute("SELECT is_banned FROM users WHERE user_id = ?", (user_id,))
        user = await cursor.fetchone()
        if user:
            new_status = 0 if user["is_banned"] else 1
            await db.execute("UPDATE users SET is_banned = ? WHERE user_id = ?", (new_status, user_id))
            await db.commit()
            await bot.answer_callback_query(call.id, f"✅ Пользователь {'разбанен' if new_status == 0 else 'забанен'}!")
            await admin_user_callback(call)


@bot.callback_query_handler(func=lambda c: c.data.startswith("admin:change_balance:"))
async def admin_change_balance_callback(call: CallbackQuery):
    """Change user balance."""
    if not is_admin(call.from_user.id):
        return
    
    user_id = int(call.data.split(":")[2])
    user_states[call.from_user.id] = {"state": "admin_change_balance", "target_user": user_id}
    
    await bot.edit_message_text(
        f"💰 <b>Изменение баланса пользователя {user_id}</b>\n\nВведите сумму (с минусом для списания):",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=cancel_keyboard(f"admin:user:{user_id}")
    )


@bot.callback_query_handler(func=lambda c: c.data.startswith("admin:user_transactions:"))
async def admin_user_transactions_callback(call: CallbackQuery):
    """Show user transactions."""
    if not is_admin(call.from_user.id):
        return
    
    user_id = int(call.data.split(":")[2])
    transactions = await get_user_transactions(user_id, 30)
    
    text = f"📜 <b>Транзакции пользователя {user_id}</b>\n\n"
    for t in transactions:
        status_emoji = {"completed": "✅", "pending": "⏳", "failed": "❌", "cancelled": "🚫"}.get(t["status"], "❓")
        sign = "+" if t["amount"] > 0 else ""
        text += f"{status_emoji} {sign}{t['amount']:.2f}₽ — {t['type']} ({t['payment_provider'] or 'balance'})\n"
        text += f"   {t['description'] or ''}\n   📅 {t['created_at'][:16]}\n\n"
    
    await bot.edit_message_text(
        text,
        call.message.chat.id,
        call.message.message_id,
        reply_markup=admin_user_keyboard(user_id, False)
    )


@bot.callback_query_handler(func=lambda c: c.data == "admin:add_proxy")
async def admin_add_proxy_callback(call: CallbackQuery):
    """Start adding proxy."""
    if not is_admin(call.from_user.id):
        return
    
    user_states[call.from_user.id] = {"state": "admin_add_proxy", "step": 1, "data": {}}
    
    await bot.edit_message_text(
        "➕ <b>Добавление прокси (шаг 1/7)</b>\n\nВведите IP адрес:",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=cancel_keyboard("admin:panel")
    )


@bot.callback_query_handler(func=lambda c: c.data == "admin:settings")
async def admin_settings_callback(call: CallbackQuery):
    """Show settings."""
    if not is_admin(call.from_user.id):
        return
    
    welcome = await get_setting("welcome_message")
    countries = await get_setting("countries")
    types = await get_setting("proxy_types")
    
    text = (
        f"⚙️ <b>Настройки</b>\n\n"
        f"📝 Приветствие: {'Установлено' if welcome else 'По умолчанию'}\n"
        f"🌍 Страны: {countries}\n"
        f"🔧 Типы: {types}\n\n"
        f"Используйте команды для изменения:\n"
        f"/set_welcome <текст>\n"
        f"/set_countries <список через запятую>\n"
        f"/set_types <список через запятую>"
    )
    
    await bot.edit_message_text(
        text,
        call.message.chat.id,
        call.message.message_id,
        reply_markup=admin_keyboard()
    )


# ==================== Text Message Handler for States ====================

@bot.message_handler(func=lambda m: m.from_user.id in user_states)
async def state_handler(message: Message):
    """Handle multi-step user states."""
    state = user_states.get(message.from_user.id, {})
    state_type = state.get("state")
    
    if state_type == "waiting_deposit_amount":
        try:
            amount = float(message.text.replace(",", "."))
            if amount < config.MIN_DEPOSIT:
                await bot.send_message(message.chat.id, f"❌ Минимальная сумма: {config.MIN_DEPOSIT}₽")
                return
            
            payment = await process_deposit(message.from_user.id, amount)
            del user_states[message.from_user.id]
            
            await bot.send_message(
                message.chat.id,
                f"💳 <b>Пополнение на {amount} {'USDT' if config.PAYMENT_PROVIDER == 'cryptobot' else 'RUB'}</b>\n\nПерейдите по ссылке:",
                reply_markup=payment_keyboard(amount, payment["payment_id"], config.PAYMENT_PROVIDER)
            )
        except ValueError:
            await bot.send_message(message.chat.id, "❌ Введите корректное число")
    
    elif state_type == "admin_change_balance":
        try:
            amount = float(message.text.replace(",", "."))
            target_user = state["target_user"]
            
            await update_balance(target_user, amount)
            await create_transaction(target_user, amount, "deposit" if amount > 0 else "withdrawal",
                                   "admin", None, f"Админское изменение баланса: {amount:+.2f}₽")
            
            del user_states[message.from_user.id]
            await bot.send_message(message.chat.id, f"✅ Баланс пользователя {target_user} изменен на {amount:+.2f}₽",
                                 reply_markup=admin_user_keyboard(target_user, False))
        except ValueError:
            await bot.send_message(message.chat.id, "❌ Введите корректное число")
    
    elif state_type == "admin_add_proxy":
        step = state["step"]
        data = state["data"]
        
        if step == 1:
            data["ip"] = message.text.strip()
            state["step"] = 2
            await bot.send_message(message.chat.id, "🔌 Введите порт:", reply_markup=cancel_keyboard("admin:panel"))
        elif step == 2:
            try:
                data["port"] = int(message.text.strip())
                state["step"] = 3
                await bot.send_message(message.chat.id, "🌍 Введите страну (код, например RU):", reply_markup=cancel_keyboard("admin:panel"))
            except ValueError:
                await bot.send_message(message.chat.id, "❌ Порт должен быть числом")
        elif step == 3:
            data["country"] = message.text.strip().upper()
            state["step"] = 4
            await bot.send_message(message.chat.id, "🏙 Введите город (или - для пропуска):", reply_markup=cancel_keyboard("admin:panel"))
        elif step == 4:
            data["city"] = None if message.text.strip() == "-" else message.text.strip()
            state["step"] = 5
            await bot.send_message(message.chat.id, "🔧 Введите тип (http/https/socks4/socks5):", reply_markup=cancel_keyboard("admin:panel"))
        elif step == 5:
            proxy_type = message.text.strip().lower()
            if proxy_type not in ["http", "https", "socks4", "socks5"]:
                await bot.send_message(message.chat.id, "❌ Неверный тип. Используйте: http, https, socks4, socks5")
                return
            data["type"] = proxy_type
            state["step"] = 6
            await bot.send_message(message.chat.id, "💰 Введите цену за день (или 0):", reply_markup=cancel_keyboard("admin:panel"))
        elif step == 6:
            try:
                data["price_per_day"] = float(message.text.replace(",", "."))
                state["step"] = 7
                await bot.send_message(message.chat.id, "💰 Введите цену за неделю (или 0):", reply_markup=cancel_keyboard("admin:panel"))
            except ValueError:
                await bot.send_message(message.chat.id, "❌ Введите число")
        elif step == 7:
            try:
                data["price_per_week"] = float(message.text.replace(",", "."))
                # Save proxy
                await add_proxy(
                    data["ip"], data["port"], data["country"], data["city"],
                    proxy_type=data["type"], price_per_day=data["price_per_day"],
                    price_per_week=data["price_per_week"], price_per_month=data["price_per_week"] * 4,
                    seller_id=message.from_user.id
                )
                del user_states[message.from_user.id]
                await bot.send_message(message.chat.id, "✅ Прокси успешно добавлен!", reply_markup=admin_keyboard())
            except ValueError:
                await bot.send_message(message.chat.id, "❌ Введите число")


# ==================== Admin Commands ====================

@bot.message_handler(commands=["set_welcome"])
async def set_welcome_command(message: Message):
    """Set welcome message."""
    if not is_admin(message.from_user.id):
        return
    
    text = message.text.split(" ", 1)
    if len(text) < 2:
        await bot.send_message(message.chat.id, "Использование: /set_welcome <текст>")
        return
    
    await set_setting("welcome_message", text[1])
    await bot.send_message(message.chat.id, "✅ Приветствие обновлено!")


@bot.message_handler(commands=["set_countries"])
async def set_countries_command(message: Message):
    """Set available countries."""
    if not is_admin(message.from_user.id):
        return
    
    text = message.text.split(" ", 1)
    if len(text) < 2:
        await bot.send_message(message.chat.id, "Использование: /set_countries RU,US,DE,...")
        return
    
    await set_setting("countries", text[1])
    await bot.send_message(message.chat.id, "✅ Список стран обновлен!")


@bot.message_handler(commands=["set_types"])
async def set_types_command(message: Message):
    """Set proxy types."""
    if not is_admin(message.from_user.id):
        return
    
    text = message.text.split(" ", 1)
    if len(text) < 2:
        await bot.send_message(message.chat.id, "Использование: /set_types http,https,socks5")
        return
    
    await set_setting("proxy_types", text[1])
    await bot.send_message(message.chat.id, "✅ Список типов обновлен!")


@bot.message_handler(commands=["broadcast"])
async def broadcast_command(message: Message):
    """Broadcast message to all users."""
    if not is_admin(message.from_user.id):
        return
    
    text = message.text.split(" ", 1)
    if len(text) < 2:
        await bot.send_message(message.chat.id, "Использование: /broadcast <текст>")
        return
    
    from database import get_db
    async with get_db() as db:
        cursor = await db.execute("SELECT user_id FROM users WHERE is_banned = 0")
        users = await cursor.fetchall()
    
    sent = 0
    for user in users:
        try:
            await bot.send_message(user["user_id"], text[1])
            sent += 1
        except Exception:
            pass
    
    await bot.send_message(message.chat.id, f"✅ Рассылка отправлена {sent} пользователям.")


# ==================== Inline Query (for referral sharing) ====================

@bot.inline_handler(func=lambda q: True)
async def inline_query_handler(inline_query: InlineQuery):
    """Handle inline queries for referral sharing."""
    user = await get_user(inline_query.from_user.id)
    if not user:
        return
    
    bot_info = await bot.get_me()
    referral_link = f"https://t.me/{bot_info.username}?start=ref_{user['referral_code']}"
    
    result = InlineQueryResultArticle(
        id="referral",
        title="🔗 Моя реферальная ссылка",
        description=f"Пригласите друзей и получите {config.REFERRAL_BONUS_PERCENT}% от их пополнений",
        input_message_content=InputTextMessageContent(
            f"👥 Присоединяйся к Proxy Shop Bot по моей ссылке!\n\n{referral_link}\n\n🎁 Получи бонус на первое пополнение!",
            parse_mode="HTML"
        )
    )
    
    await bot.answer_inline_query(inline_query.id, [result], cache_time=1)


# ==================== Callback Router ====================

@bot.callback_query_handler(func=lambda c: c.data == "main_menu")
async def main_menu_callback(call: CallbackQuery):
    """Return to main menu."""
    await bot.edit_message_text(
        "🏠 Главное меню:",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=main_menu_keyboard(call.from_user.id)
    )


@bot.callback_query_handler(func=lambda c: c.data == "cancel")
async def cancel_callback(call: CallbackQuery):
    """Cancel current operation."""
    if call.from_user.id in user_states:
        del user_states[call.from_user.id]
    await bot.edit_message_text("❌ Отменено.", call.message.chat.id, call.message.message_id,
                               reply_markup=main_menu_keyboard(call.from_user.id))


# ==================== Error Handler ====================

@bot.middleware_handler(update_types=["message", "callback_query"])
async def check_ban_middleware(bot_instance, update):
    """Check if user is banned."""
    user_id = update.from_user.id if hasattr(update, 'from_user') else None
    if user_id:
        user = await get_user(user_id)
        if user and user["is_banned"]:
            if hasattr(update, 'message'):
                await bot.send_message(update.message.chat.id, "🚫 Вы заблокированы.")
            elif hasattr(update, 'callback_query'):
                await bot.answer_callback_query(update.callback_query.id, "🚫 Вы заблокированы.", show_alert=True)
            return False
    return True