import asyncio
from datetime import datetime, timedelta
from telebot import TeleBot
from telebot.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy import select, func, desc
from sqlalchemy.orm import selectinload

from database import (
    User, Proxy, Order, Transaction, ProxyType, ProxyStatus, OrderStatus, TransactionType,
    AsyncSessionLocal, init_db
)
from config import config
from keyboards import (
    get_main_menu_keyboard, get_cancel_keyboard, get_proxy_types_keyboard,
    get_countries_keyboard, get_count_keyboard, get_period_keyboard,
    get_payment_keyboard, get_profile_keyboard, get_deposit_amounts_keyboard,
    get_my_proxies_keyboard, get_proxy_info_keyboard, get_reply_keyboard_remove,
    get_pagination_keyboard,
)
from payments.yookassa_client import yookassa_client, PaymentResult
from proxy.proxy6_client import proxy6_client, Proxy6Type, Proxy6Country, buy_proxies_for_user, get_proxy_price, get_available_countries
from utils.states import UserState, user_states


# --- Helper functions ---

async def get_or_create_user(session, message: Message) -> User:
    """Get or create user from message"""
    user = await session.get(User, message.from_user.id)
    if not user:
        user = User(
            id=message.from_user.id,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
            last_name=message.from_user.last_name,
            language_code=message.from_user.language_code or "ru",
            referral_code=f"ref_{message.from_user.id}",
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
    else:
        # Update info
        user.username = message.from_user.username
        user.first_name = message.from_user.first_name
        user.last_name = message.from_user.last_name
        await session.commit()
    return user


async def send_main_menu(bot: TeleBot, chat_id: int, user_id: int, text: str = "Главное меню:"):
    """Send main menu"""
    await bot.send_message(
        chat_id,
        text,
        reply_markup=get_main_menu_keyboard(user_id),
    )


def format_proxy_info(proxy: Proxy) -> str:
    """Format proxy info for display"""
    status_emoji = {
        ProxyStatus.AVAILABLE: "🟢",
        ProxyStatus.SOLD: "✅",
        ProxyStatus.EXPIRED: "🔴",
        ProxyStatus.PENDING: "🟡",
    }.get(proxy.status, "⚪")

    auth = f"{proxy.login}:{proxy.password}@" if proxy.login and proxy.password else ""
    return (
        f"{status_emoji} <b>Прокси #{proxy.id}</b>\n"
        f"🔗 <code>{proxy.type.value}://{auth}{proxy.ip}:{proxy.port}</code>\n"
        f"🌍 Страна: {proxy.country or 'Неизвестно'} {proxy.city and f'({proxy.city})' or ''}\n"
        f"🏢 Провайдер: {proxy.isp or 'Неизвестно'}\n"
        f"💰 Цена: {proxy.sale_price:.2f} ₽/мес\n"
        f"📅 До: {proxy.expires_at.strftime('%d.%m.%Y %H:%M') if proxy.expires_at else 'Не указано'}\n"
        f"Статус: {proxy.status.value}"
    )


# --- Command Handlers ---

def register_user_handlers(bot: TeleBot):

    @bot.message_handler(commands=['start'])
    async def cmd_start(message: Message):
        async with AsyncSessionLocal() as session:
            user = await get_or_create_user(session, message)

            # Check referral
            args = message.text.split()
            if len(args) > 1 and args[1].startswith("ref_"):
                try:
                    ref_id = int(args[1][4:])
                    if ref_id != user.id and not user.referred_by:
                        referrer = await session.get(User, ref_id)
                        if referrer:
                            user.referred_by = ref_id
                            # Give bonus to referrer
                            referrer.balance += config.REFERRAL_BONUS
                            session.add(Transaction(
                                user_id=referrer.id,
                                type=TransactionType.REFERRAL,
                                amount=config.REFERRAL_BONUS,
                                balance_before=referrer.balance - config.REFERRAL_BONUS,
                                balance_after=referrer.balance,
                                description=f"Реферальный бонус от @{user.username or user.id}",
                            ))
                            await session.commit()
                            await bot.send_message(
                                referrer.id,
                                f"🎁 Новый реферал @{user.username or user.id}!\n"
                                f"Начислено {config.REFERRAL_BONUS} ₽ на баланс."
                            )
                except (ValueError, TypeError):
                    pass

            # Check if banned
            if user.is_banned:
                await bot.send_message(message.chat.id, "🚫 Вы заблокированы.")
                return

            welcome_text = (
                f"👋 Добро пожаловать, {user.first_name or 'друг'}!\n\n"
                f"Это бот для покупки прокси (HTTP/HTTPS/SOCKS5).\n"
                f"💰 Ваш баланс: <b>{user.balance:.2f} ₽</b>\n\n"
                f"Выберите действие в меню ниже:"
            )
            await send_main_menu(bot, message.chat.id, user.id, welcome_text)

    @bot.message_handler(commands=['menu'])
    async def cmd_menu(message: Message):
        async with AsyncSessionLocal() as session:
            user = await session.get(User, message.from_user.id)
            if not user or user.is_banned:
                return
            await send_main_menu(bot, message.chat.id, user.id)

    @bot.message_handler(commands=['profile'])
    async def cmd_profile(message: Message):
        async with AsyncSessionLocal() as session:
            user = await session.get(User, message.from_user.id)
            if not user or user.is_banned:
                return

            # Stats
            orders_count = await session.scalar(
                select(func.count(Order.id)).where(Order.user_id == user.id)
            )
            proxies_count = await session.scalar(
                select(func.count(Proxy.id)).where(Proxy.user_id == user.id)
            )
            active_proxies = await session.scalar(
                select(func.count(Proxy.id)).where(
                    Proxy.user_id == user.id,
                    Proxy.status == ProxyStatus.SOLD
                )
            )

            ref_link = f"https://t.me/{(await bot.get_me()).username}?start=ref_{user.id}"

            text = (
                f"👤 <b>Профиль</b>\n\n"
                f"🆔 ID: <code>{user.id}</code>\n"
                f"👤 Имя: {user.first_name or ''} {user.last_name or ''}\n"
                f"🔗 Username: @{user.username or 'не указан'}\n"
                f"💰 Баланс: <b>{user.balance:.2f} ₽</b>\n"
                f"📦 Заказов: {orders_count}\n"
                f"🔌 Прокси всего: {proxies_count}\n"
                f"✅ Активных: {active_proxies}\n"
                f"🎁 Реф. код: <code>{user.referral_code}</code>\n"
                f"🔗 Реф. ссылка: {ref_link}\n"
                f"📅 Регистрация: {user.created_at.strftime('%d.%m.%Y')}"
            )
            await bot.send_message(
                message.chat.id,
                text,
                parse_mode="HTML",
                reply_markup=get_profile_keyboard()
            )

    @bot.message_handler(commands=['myproxies'])
    async def cmd_my_proxies(message: Message):
        await show_my_proxies(bot, message.chat.id, message.from_user.id, page=0)

    @bot.message_handler(commands=['balance'])
    async def cmd_balance(message: Message):
        async with AsyncSessionLocal() as session:
            user = await session.get(User, message.from_user.id)
            if not user or user.is_banned:
                return
            await bot.send_message(
                message.chat.id,
                f"💰 Ваш баланс: <b>{user.balance:.2f} ₽</b>",
                parse_mode="HTML",
                reply_markup=get_profile_keyboard()
            )

    # --- Text Message Handlers (Reply Keyboard) ---

    @bot.message_handler(func=lambda m: m.text == "🛒 Купить прокси")
    async def btn_buy_proxy(message: Message):
        async with AsyncSessionLocal() as session:
            user = await session.get(User, message.from_user.id)
            if not user or user.is_banned:
                return

            user_states[user.id] = UserState.CHOOSING_PROXY_TYPE
            await bot.send_message(
                message.chat.id,
                "🌐 Выберите тип прокси:",
                reply_markup=get_proxy_types_keyboard()
            )

    @bot.message_handler(func=lambda m: m.text == "📦 Мои прокси")
    async def btn_my_proxies(message: Message):
        await show_my_proxies(bot, message.chat.id, message.from_user.id, page=0)

    @bot.message_handler(func=lambda m: m.text == "👤 Профиль")
    async def btn_profile(message: Message):
        await cmd_profile(message)

    @bot.message_handler(func=lambda m: m.text == "💳 Пополнить баланс")
    async def btn_deposit(message: Message):
        await show_deposit_menu(bot, message.chat.id, message.from_user.id)

    @bot.message_handler(func=lambda m: m.text == "ℹ️ Помощь")
    async def btn_help(message: Message):
        help_text = (
            "ℹ️ <b>Помощь</b>\n\n"
            "🛒 <b>Купить прокси</b> — выберите тип, страну, количество и срок аренды.\n"
            "📦 <b>Мои прокси</b> — список купленных прокси с данными для подключения.\n"
            "👤 <b>Профиль</b> — баланс, статистика, реферальная ссылка.\n"
            "💳 <b>Пополнить баланс</b> — оплата через ЮKassa (банковские карты, СБП).\n"
            "🎁 <b>Реферальная программа</b> — приглашайте друзей и получайте бонусы.\n\n"
            "💡 <b>Советы:</b>\n"
            "• Минимальное пополнение: 100 ₽\n"
            "• Прокси выдаются автоматически после оплаты\n"
            "• Поддержка: @support_username\n\n"
            "🔧 Типы прокси:\n"
            "• <b>HTTP/HTTPS</b> — для браузеров, парсеров, соцсетей\n"
            "• <b>SOCKS5</b> — для программ, игр, Telegram-клиентов"
        )
        await bot.send_message(message.chat.id, help_text, parse_mode="HTML")

    @bot.message_handler(func=lambda m: m.text == "🎁 Реферальная программа")
    async def btn_referral(message: Message):
        async with AsyncSessionLocal() as session:
            user = await session.get(User, message.from_user.id)
            if not user or user.is_banned:
                return

            referrals_count = await session.scalar(
                select(func.count(User.id)).where(User.referred_by == user.id)
            )
            ref_earnings = await session.scalar(
                select(func.coalesce(func.sum(Transaction.amount), 0)).where(
                    Transaction.user_id == user.id,
                    Transaction.type == TransactionType.REFERRAL
                )
            )

            ref_link = f"https://t.me/{(await bot.get_me()).username}?start=ref_{user.id}"

            text = (
                f"🎁 <b>Реферальная программа</b>\n\n"
                f"Приглашайте друзей и получайте <b>{config.REFERRAL_BONUS} ₽</b> за каждого!\n\n"
                f"🔗 Ваша ссылка:\n<code>{ref_link}</code>\n\n"
                f"👥 Приглашено: {referrals_count}\n"
                f"💰 Заработано: {ref_earnings:.2f} ₽\n\n"
                f"Бонус начисляется после первого пополнения реферала."
            )
            await bot.send_message(
                message.chat.id,
                text,
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup().add(
                    InlineKeyboardButton("📋 Скопировать ссылку", callback_data=f"copy_ref_link:{user.id}")
                )
            )

    # --- Admin entry from main menu ---
    @bot.message_handler(func=lambda m: m.text == "⚙️ Админ-панель")
    async def btn_admin_panel(message: Message):
        if message.from_user.id not in config.ADMIN_IDS:
            return
        from handlers.admin_handlers import show_admin_main
        await show_admin_main(bot, message.chat.id)

    # --- Callback Handlers ---

    @bot.callback_query_handler(func=lambda c: c.data == "cancel")
    async def cb_cancel(callback: CallbackQuery):
        user_id = callback.from_user.id
        user_states.pop(user_id, None)
        await bot.edit_message_text(
            "❌ Отменено",
            callback.message.chat.id,
            callback.message.message_id,
        )
        await send_main_menu(bot, callback.message.chat.id, user_id)

    @bot.callback_query_handler(func=lambda c: c.data.startswith("proxy_type:"))
    async def cb_proxy_type(callback: CallbackQuery):
        user_id = callback.from_user.id
        proxy_type = callback.data.split(":")[1]

        async with AsyncSessionLocal() as session:
            user = await session.get(User, user_id)
            if not user or user.is_banned:
                return

        user_states[user_id] = UserState.CHOOSING_COUNTRY
        user_states[f"{user_id}_proxy_type"] = proxy_type

        # Get countries from Proxy6
        try:
            countries = await get_available_countries(proxy_type)
            if not countries:
                await bot.edit_message_text(
                    "❌ Нет доступных стран для этого типа прокси",
                    callback.message.chat.id,
                    callback.message.message_id,
                )
                return

            await bot.edit_message_text(
                f"🌍 Выберите страну для {proxy_type.upper()} прокси:",
                callback.message.chat.id,
                callback.message.message_id,
                reply_markup=get_countries_keyboard(countries, proxy_type)
            )
        except Exception as e:
            await bot.edit_message_text(
                f"❌ Ошибка получения стран: {e}",
                callback.message.chat.id,
                callback.message.message_id,
            )

    @bot.callback_query_handler(func=lambda c: c.data.startswith("countries_page:"))
    async def cb_countries_page(callback: CallbackQuery):
        _, proxy_type, page = callback.data.split(":")
        page = int(page)

        try:
            countries = await get_available_countries(proxy_type)
            await bot.edit_message_reply_markup(
                callback.message.chat.id,
                callback.message.message_id,
                reply_markup=get_countries_keyboard(countries, proxy_type, page)
            )
        except Exception as e:
            await bot.answer_callback_query(callback.id, f"Ошибка: {e}")

    @bot.callback_query_handler(func=lambda c: c.data.startswith("country:"))
    async def cb_country(callback: CallbackQuery):
        user_id = callback.from_user.id
        _, proxy_type, country = callback.data.split(":")

        user_states[user_id] = UserState.CHOOSING_COUNT
        user_states[f"{user_id}_country"] = country

        await bot.edit_message_text(
            f"🔢 Выберите количество {proxy_type.upper()} прокси из {country.upper()}:",
            callback.message.chat.id,
            callback.message.message_id,
            reply_markup=get_count_keyboard(proxy_type, country)
        )

    @bot.callback_query_handler(func=lambda c: c.data.startswith("count:"))
    async def cb_count(callback: CallbackQuery):
        user_id = callback.from_user.id
        _, proxy_type, country, count = callback.data.split(":")
        count = int(count)

        user_states[user_id] = UserState.CHOOSING_PERIOD
        user_states[f"{user_id}_count"] = count

        await bot.edit_message_text(
            f"📅 Выберите срок аренды для {count} {proxy_type.upper()} прокси ({country.upper()}):",
            callback.message.chat.id,
            callback.message.message_id,
            reply_markup=get_period_keyboard(proxy_type, country, count)
        )

    @bot.callback_query_handler(func=lambda c: c.data.startswith("period:"))
    async def cb_period(callback: CallbackQuery):
        user_id = callback.from_user.id
        _, proxy_type, country, count, period = callback.data.split(":")
        count = int(count)
        period = int(period)

        # Calculate price
        try:
            price = await get_proxy_price(proxy_type, country, count, period)
            markup_price = price * (1 + config.PROXY_MARKUP_PERCENT)
        except Exception as e:
            await bot.edit_message_text(
                f"❌ Ошибка расчета цены: {e}",
                callback.message.chat.id,
                callback.message.message_id,
            )
            return

        async with AsyncSessionLocal() as session:
            user = await session.get(User, user_id)
            if not user or user.is_banned:
                return

            # Create pending order
            order = Order(
                user_id=user.id,
                proxy_type=ProxyType(proxy_type),
                country=country,
                count=count,
                period_days=period,
                total_price=markup_price,
                status=OrderStatus.PENDING,
            )
            session.add(order)
            await session.commit()
            await session.refresh(order)

            # Create payment
            try:
                payment = yookassa_client.create_payment(
                    amount=markup_price,
                    description=f"Прокси {proxy_type.upper()} x{count} ({country.upper()}) на {period} дней",
                    metadata={
                        "order_id": order.id,
                        "user_id": user.id,
                        "type": "proxy_purchase",
                    },
                )
                order.yookassa_payment_id = payment.payment_id
                order.yookassa_payment_url = payment.confirmation_url
                await session.commit()
            except Exception as e:
                await bot.edit_message_text(
                    f"❌ Ошибка создания платежа: {e}",
                    callback.message.chat.id,
                    callback.message.message_id,
                )
                return

        text = (
            f"📋 <b>Заказ #{order.id}</b>\n\n"
            f"🌐 Тип: {proxy_type.upper()}\n"
            f"🌍 Страна: {country.upper()}\n"
            f"🔢 Количество: {count}\n"
            f"📅 Срок: {period} дней\n"
            f"💰 К оплате: <b>{markup_price:.2f} ₽</b>\n\n"
            f"Нажмите кнопку ниже для оплаты:"
        )
        await bot.edit_message_text(
            text,
            callback.message.chat.id,
            callback.message.message_id,
            parse_mode="HTML",
            reply_markup=get_payment_keyboard(payment.confirmation_url, order.id)
        )

    @bot.callback_query_handler(func=lambda c: c.data.startswith("check_payment:"))
    async def cb_check_payment(callback: CallbackQuery):
        user_id = callback.from_user.id
        order_id = int(callback.data.split(":")[1])

        async with AsyncSessionLocal() as session:
            order = await session.get(Order, order_id)
            if not order or order.user_id != user_id:
                await bot.answer_callback_query(callback.id, "Заказ не найден")
                return

            if not order.yookassa_payment_id:
                await bot.answer_callback_query(callback.id, "Платеж не создан")
                return

            try:
                payment = yookassa_client.get_payment(order.yookassa_payment_id)
                if payment.status == "succeeded":
                    await fulfill_order(bot, session, order)
                    await bot.edit_message_text(
                        f"✅ Оплата прошла успешно! Прокси выданы.\n\n{await get_order_proxies_text(session, order)}",
                        callback.message.chat.id,
                        callback.message.message_id,
                        parse_mode="HTML",
                    )
                elif payment.status == "pending":
                    await bot.answer_callback_query(callback.id, "⏳ Платеж еще не обработан, попробуйте позже")
                else:
                    await bot.answer_callback_query(callback.id, f"❌ Статус платежа: {payment.status}")
            except Exception as e:
                await bot.answer_callback_query(callback.id, f"Ошибка проверки: {e}")

    @bot.callback_query_handler(func=lambda c: c.data.startswith("cancel_order:"))
    async def cb_cancel_order(callback: CallbackQuery):
        user_id = callback.from_user.id
        order_id = int(callback.data.split(":")[1])

        async with AsyncSessionLocal() as session:
            order = await session.get(Order, order_id)
            if not order or order.user_id != user_id:
                await bot.answer_callback_query(callback.id, "Заказ не найден")
                return

            if order.status in [OrderStatus.COMPLETED, OrderStatus.PAID]:
                await bot.answer_callback_query(callback.id, "Нельзя отменить оплаченный заказ")
                return

            order.status = OrderStatus.FAILED
            await session.commit()

        await bot.edit_message_text(
            "❌ Заказ отменен",
            callback.message.chat.id,
            callback.message.message_id,
        )

    @bot.callback_query_handler(func=lambda c: c.data == "deposit")
    async def cb_deposit(callback: CallbackQuery):
        await show_deposit_menu(bot, callback.message.chat.id, callback.from_user.id)

    @bot.callback_query_handler(func=lambda c: c.data == "my_orders")
    async def cb_my_orders(callback: CallbackQuery):
        await show_my_orders(bot, callback.message.chat.id, callback.from_user.id, page=0)

    @bot.callback_query_handler(func=lambda c: c.data == "referral")
    async def cb_referral(callback: CallbackQuery):
        async with AsyncSessionLocal() as session:
            user = await session.get(User, callback.from_user.id)
            if not user:
                return

            referrals_count = await session.scalar(
                select(func.count(User.id)).where(User.referred_by == user.id)
            )
            ref_earnings = await session.scalar(
                select(func.coalesce(func.sum(Transaction.amount), 0)).where(
                    Transaction.user_id == user.id,
                    Transaction.type == TransactionType.REFERRAL
                )
            )

            ref_link = f"https://t.me/{(await bot.get_me()).username}?start=ref_{user.id}"

            text = (
                f"🎁 <b>Реферальная программа</b>\n\n"
                f"Приглашайте друзей и получайте <b>{config.REFERRAL_BONUS} ₽</b> за каждого!\n\n"
                f"🔗 Ваша ссылка:\n<code>{ref_link}</code>\n\n"
                f"👥 Приглашено: {referrals_count}\n"
                f"💰 Заработано: {ref_earnings:.2f} ₽"
            )
            await bot.edit_message_text(
                text,
                callback.message.chat.id,
                callback.message.message_id,
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup().add(
                    InlineKeyboardButton("📋 Скопировать", callback_data=f"copy_ref_link:{user.id}"),
                    InlineKeyboardButton("🔙 Назад", callback_data="profile"),
                )
            )

    @bot.callback_query_handler(func=lambda c: c.data.startswith("copy_ref_link:"))
    async def cb_copy_ref_link(callback: CallbackQuery):
        user_id = int(callback.data.split(":")[1])
        ref_link = f"https://t.me/{(await bot.get_me()).username}?start=ref_{user_id}"
        await bot.answer_callback_query(callback.id, "Ссылка скопирована!", show_alert=True)

    @bot.callback_query_handler(func=lambda c: c.data == "change_ref_code")
    async def cb_change_ref_code(callback: CallbackQuery):
        user_id = callback.from_user.id
        user_states[user_id] = UserState.CHANGING_REF_CODE
        await bot.edit_message_text(
            "🔑 Введите новый реферальный код (только латиница и цифры, 5-20 символов):",
            callback.message.chat.id,
            callback.message.message_id,
            reply_markup=InlineKeyboardMarkup().add(
                InlineKeyboardButton("❌ Отмена", callback_data="profile")
            )
        )

    @bot.callback_query_handler(func=lambda c: c.data.startswith("deposit_amount:"))
    async def cb_deposit_amount(callback: CallbackQuery):
        user_id = callback.from_user.id
        amount = int(callback.data.split(":")[1])
        await create_deposit_payment(bot, callback.message.chat.id, user_id, amount)

    @bot.callback_query_handler(func=lambda c: c.data == "deposit_custom")
    async def cb_deposit_custom(callback: CallbackQuery):
        user_id = callback.from_user.id
        user_states[user_id] = UserState.ENTERING_DEPOSIT_AMOUNT
        await bot.edit_message_text(
            f"💰 Введите сумму пополнения (мин. {config.MIN_DEPOSIT} ₽):",
            callback.message.chat.id,
            callback.message.message_id,
            reply_markup=InlineKeyboardMarkup().add(
                InlineKeyboardButton("❌ Отмена", callback_data="deposit")
            )
        )

    @bot.callback_query_handler(func=lambda c: c.data == "my_proxies")
    async def cb_my_proxies(callback: CallbackQuery):
        await show_my_proxies(bot, callback.message.chat.id, callback.from_user.id, page=0)

    @bot.callback_query_handler(func=lambda c: c.data.startswith("my_proxies_page:"))
    async def cb_my_proxies_page(callback: CallbackQuery):
        user_id = callback.from_user.id
        page = int(callback.data.split(":")[1])
        await show_my_proxies(bot, callback.message.chat.id, user_id, page)

    @bot.callback_query_handler(func=lambda c: c.data.startswith("proxy_info:"))
    async def cb_proxy_info(callback: CallbackQuery):
        user_id = callback.from_user.id
        proxy_id = int(callback.data.split(":")[1])

        async with AsyncSessionLocal() as session:
            proxy = await session.get(Proxy, proxy_id)
            if not proxy or proxy.user_id != user_id:
                await bot.answer_callback_query(callback.id, "Прокси не найдено")
                return

            text = format_proxy_info(proxy)
            await bot.edit_message_text(
                text,
                callback.message.chat.id,
                callback.message.message_id,
                parse_mode="HTML",
                reply_markup=get_proxy_info_keyboard(proxy.id)
            )

    @bot.callback_query_handler(func=lambda c: c.data.startswith("copy_proxy:"))
    async def cb_copy_proxy(callback: CallbackQuery):
        user_id = callback.from_user.id
        proxy_id = int(callback.data.split(":")[1])

        async with AsyncSessionLocal() as session:
            proxy = await session.get(Proxy, proxy_id)
            if not proxy or proxy.user_id != user_id:
                await bot.answer_callback_query(callback.id, "Прокси не найдено")
                return

            conn_str = proxy.connection_string
            await bot.answer_callback_query(
                callback.id,
                f"Скопировано: {conn_str}",
                show_alert=True
            )

    @bot.callback_query_handler(func=lambda c: c.data.startswith("renew_proxy:"))
    async def cb_renew_proxy(callback: CallbackQuery):
        user_id = callback.from_user.id
        proxy_id = int(callback.data.split(":")[1])

        async with AsyncSessionLocal() as session:
            proxy = await session.get(Proxy, proxy_id)
            if not proxy or proxy.user_id != user_id:
                await bot.answer_callback_query(callback.id, "Прокси не найдено")
                return

            # Show renewal options
            kb = InlineKeyboardMarkup(row_width=2)
            for days in [7, 30, 60, 90]:
                price = proxy.sale_price * (days / 30)
                kb.add(InlineKeyboardButton(
                    f"{days} дней - {price:.2f} ₽",
                    callback_data=f"renew_confirm:{proxy_id}:{days}"
                ))
            kb.add(InlineKeyboardButton("❌ Отмена", callback_data=f"proxy_info:{proxy_id}"))

            await bot.edit_message_text(
                f"🔄 Продление прокси {proxy.ip}:{proxy.port}\n"
                f"Текущий срок до: {proxy.expires_at.strftime('%d.%m.%Y') if proxy.expires_at else 'Неизвестно'}\n\n"
                f"Выберите срок:",
                callback.message.chat.id,
                callback.message.message_id,
                reply_markup=kb
            )

    @bot.callback_query_handler(func=lambda c: c.data.startswith("renew_confirm:"))
    async def cb_renew_confirm(callback: CallbackQuery):
        user_id = callback.from_user.id
        _, proxy_id, days = callback.data.split(":")
        proxy_id = int(proxy_id)
        days = int(days)

        async with AsyncSessionLocal() as session:
            proxy = await session.get(Proxy, proxy_id)
            if not proxy or proxy.user_id != user_id:
                await bot.answer_callback_query(callback.id, "Прокси не найдено")
                return

            price = proxy.sale_price * (days / 30)

            if user.balance < price:
                await bot.answer_callback_query(callback.id, "Недостаточно средств на балансе", show_alert=True)
                return

            # Create order for renewal
            order = Order(
                user_id=user.id,
                proxy_type=proxy.type,
                country=proxy.country,
                count=1,
                period_days=days,
                total_price=price,
                status=OrderStatus.PENDING,
            )
            session.add(order)
            await session.commit()
            await session.refresh(order)

            # Deduct from balance
            user.balance -= price
            session.add(Transaction(
                user_id=user.id,
                type=TransactionType.PURCHASE,
                amount=-price,
                balance_before=user.balance + price,
                balance_after=user.balance,
                description=f"Продление прокси {proxy.ip}:{proxy.port} на {days} дней",
                order_id=order.id,
            ))
            await session.commit()

            # Prolong via API
            try:
                success = await proxy6_client.prolong_proxy(proxy.proxy6_id, days)
                if success:
                    proxy.expires_at = (proxy.expires_at or datetime.utcnow()) + timedelta(days=days)
                    order.status = OrderStatus.COMPLETED
                    order.completed_at = datetime.utcnow()
                    await session.commit()
                    await bot.edit_message_text(
                        f"✅ Прокси продлен на {days} дней!\n"
                        f"Новый срок до: {proxy.expires_at.strftime('%d.%m.%Y')}",
                        callback.message.chat.id,
                        callback.message.message_id,
                    )
                else:
                    await bot.edit_message_text(
                        "❌ Ошибка продления у провайдера. Обратитесь в поддержку.",
                        callback.message.chat.id,
                        callback.message.message_id,
                    )
            except Exception as e:
                await bot.edit_message_text(
                    f"❌ Ошибка: {e}",
                    callback.message.chat.id,
                    callback.message.message_id,
                )

    @bot.callback_query_handler(func=lambda c: c.data.startswith("delete_proxy:"))
    async def cb_delete_proxy(callback: CallbackQuery):
        user_id = callback.from_user.id
        proxy_id = int(callback.data.split(":")[1])

        async with AsyncSessionLocal() as session:
            proxy = await session.get(Proxy, proxy_id)
            if not proxy or proxy.user_id != user_id:
                await bot.answer_callback_query(callback.id, "Прокси не найдено")
                return

            # Delete via API
            try:
                if proxy.proxy6_id:
                    await proxy6_client.delete_proxy(proxy.proxy6_id)
            except Exception:
                pass

            proxy.status = ProxyStatus.EXPIRED
            proxy.user_id = None
            await session.commit()

            await bot.edit_message_text(
                "❌ Прокси удален",
                callback.message.chat.id,
                callback.message.message_id,
            )

    # --- Profile callback ---
    @bot.callback_query_handler(func=lambda c: c.data == "profile")
    async def cb_profile(callback: CallbackQuery):
        await cmd_profile(callback.message)


# --- Helper functions ---

async def show_my_proxies(bot: TeleBot, chat_id: int, user_id: int, page: int = 0):
    async with AsyncSessionLocal() as session:
        proxies = await session.scalars(
            select(Proxy)
            .where(Proxy.user_id == user_id)
            .order_by(desc(Proxy.created_at))
        )
        proxies = list(proxies)

    if not proxies:
        await bot.send_message(
            chat_id,
            "📦 У вас пока нет прокси.\nНажмите «🛒 Купить прокси» чтобы приобрести.",
            reply_markup=get_main_menu_keyboard(user_id)
        )
        return

    await bot.send_message(
        chat_id,
        f"📦 <b>Ваши прокси ({len(proxies)})</b>:\n\nВыберите прокси для просмотра деталей:",
        parse_mode="HTML",
        reply_markup=get_my_proxies_keyboard(proxies, page)
    )


async def show_my_orders(bot: TeleBot, chat_id: int, user_id: int, page: int = 0):
    async with AsyncSessionLocal() as session:
        orders = await session.scalars(
            select(Order)
            .where(Order.user_id == user_id)
            .order_by(desc(Order.created_at))
            .limit(10)
            .offset(page * 10)
        )
        orders = list(orders)

        total = await session.scalar(
            select(func.count(Order.id)).where(Order.user_id == user_id)
        )

    if not orders:
        await bot.send_message(
            chat_id,
            "📋 У вас пока нет заказов.",
            reply_markup=InlineKeyboardMarkup().add(
                InlineKeyboardButton("🔙 Назад", callback_data="profile")
            )
        )
        return

    text = f"📋 <b>Ваши заказы ({total})</b>:\n\n"
    for order in orders:
        status_emoji = {
            OrderStatus.PENDING: "⏳",
            OrderStatus.PAID: "✅",
            OrderStatus.COMPLETED: "📦",
            OrderStatus.FAILED: "❌",
            OrderStatus.REFUNDED: "💸",
        }.get(order.status, "❓")

        text += (
            f"{status_emoji} <b>#{order.id}</b> — {order.proxy_type.value.upper()} x{order.count} "
            f"({order.country.upper()}) — {order.period_days} дн. — {order.total_price:.2f} ₽\n"
        )

    kb = InlineKeyboardMarkup()
    if page > 0:
        kb.add(InlineKeyboardButton("⬅️", callback_data=f"my_orders_page:{page-1}"))
    if (page + 1) * 10 < total:
        kb.add(InlineKeyboardButton("➡️", callback_data=f"my_orders_page:{page+1}"))
    kb.add(InlineKeyboardButton("🔙 Назад", callback_data="profile"))

    await bot.send_message(chat_id, text, parse_mode="HTML", reply_markup=kb)


async def show_deposit_menu(bot: TeleBot, chat_id: int, user_id: int):
    async with AsyncSessionLocal() as session:
        user = await session.get(User, user_id)
        if not user:
            return

    await bot.send_message(
        chat_id,
        f"💳 <b>Пополнение баланса</b>\n\n"
        f"Текущий баланс: <b>{user.balance:.2f} ₽</b>\n"
        f"Минимальная сумма: {config.MIN_DEPOSIT} ₽\n\n"
        f"Выберите сумму или введите свою:",
        parse_mode="HTML",
        reply_markup=get_deposit_amounts_keyboard()
    )


async def create_deposit_payment(bot: TeleBot, chat_id: int, user_id: int, amount: int):
    if amount < config.MIN_DEPOSIT:
        await bot.send_message(chat_id, f"❌ Минимальная сумма: {config.MIN_DEPOSIT} ₽")
        return

    async with AsyncSessionLocal() as session:
        user = await session.get(User, user_id)
        if not user:
            return

        # Create payment
        try:
            payment = yookassa_client.create_payment(
                amount=amount,
                description=f"Пополнение баланса на {amount} ₽",
                metadata={
                    "user_id": user.id,
                    "type": "deposit",
                    "amount": amount,
                },
            )
        except Exception as e:
            await bot.send_message(chat_id, f"❌ Ошибка создания платежа: {e}")
            return

        text = (
            f"💳 <b>Пополнение на {amount} ₽</b>\n\n"
            f"После оплаты средства зачислятся автоматически."
        )
        await bot.send_message(
            chat_id,
            text,
            parse_mode="HTML",
            reply_markup=get_payment_keyboard(payment.confirmation_url, 0)
        )


async def fulfill_order(bot: TeleBot, session, order: Order):
    """Fulfill order by buying proxies from provider"""
    try:
        # Buy proxies from Proxy6
        proxies = await buy_proxies_for_user(
            proxy_type=order.proxy_type.value,
            country=order.country,
            count=order.count,
            period_days=order.period_days,
        )

        if len(proxies) != order.count:
            raise Exception(f"Получено {len(proxies)} из {order.count} прокси")

        # Save proxies to DB
        for p in proxies:
            proxy = Proxy(
                proxy6_id=p.id,
                ip=p.ip,
                port=p.port,
                login=p.user,
                password=p.password,
                type=ProxyType(p.type),
                country=p.country,
                city=p.city,
                isp=p.isp,
                status=ProxyStatus.SOLD,
                price_per_month=p.price,
                sale_price=order.total_price / order.count,
                expires_at=datetime.fromisoformat(p.date_end.replace('Z', '+00:00')) if p.date_end else None,
                user_id=order.user_id,
                order_id=order.id,
            )
            session.add(proxy)

        # Update order
        order.status = OrderStatus.COMPLETED
        order.completed_at = datetime.utcnow()

        # Notify user
        user = await session.get(User, order.user_id)
        if user:
            try:
                proxy_list = "\n".join([
                    f"🔗 <code>{p.type}://{p.user}:{p.pass}@{p.ip}:{p.port}</code>"
                    for p in proxies
                ])
                await bot.send_message(
                    user.id,
                    f"✅ <b>Заказ #{order.id} выполнен!</b>\n\n"
                    f"Ваши прокси:\n{proxy_list}\n\n"
                    f"Сохраните эти данные. Они также доступны в разделе «📦 Мои прокси».",
                    parse_mode="HTML"
                )
            except Exception:
                pass

        await session.commit()
        return proxies

    except Exception as e:
        order.status = OrderStatus.FAILED
        await session.commit()
        raise


async def get_order_proxies_text(session, order: Order) -> str:
    proxies = await session.scalars(
        select(Proxy).where(Proxy.order_id == order.id)
    )
    proxies = list(proxies)
    if not proxies:
        return "Прокси не найдены"

    lines = ["📦 <b>Ваши прокси:</b>"]
    for p in proxies:
        lines.append(f"🔗 <code>{p.connection_string}</code>")
    return "\n".join(lines)


# --- Text input handlers for states ---

def register_text_handlers(bot: TeleBot):

    @bot.message_handler(func=lambda m: user_states.get(m.from_user.id) == UserState.ENTERING_DEPOSIT_AMOUNT)
    async def handle_deposit_amount(message: Message):
        user_id = message.from_user.id
        try:
            amount = int(message.text.strip())
        except ValueError:
            await bot.send_message(message.chat.id, "❌ Введите число")
            return

        user_states.pop(user_id, None)
        await create_deposit_payment(bot, message.chat.id, user_id, amount)

    @bot.message_handler(func=lambda m: user_states.get(m.from_user.id) == UserState.CHANGING_REF_CODE)
    async def handle_change_ref_code(message: Message):
        user_id = message.from_user.id
        new_code = message.text.strip()

        if not (5 <= len(new_code) <= 20 and new_code.isalnum()):
            await bot.send_message(
                message.chat.id,
                "❌ Код должен быть 5-20 символов, только латиница и цифры"
            )
            return

        async with AsyncSessionLocal() as session:
            # Check uniqueness
            existing = await session.scalar(
                select(User.id).where(User.referral_code == new_code)
            )
            if existing:
                await bot.send_message(message.chat.id, "❌ Этот код уже занят")
                return

            user = await session.get(User, user_id)
            user.referral_code = new_code
            await session.commit()

        user_states.pop(user_id, None)
        await bot.send_message(
            message.chat.id,
            f"✅ Реферальный код изменен на: <code>{new_code}</code>",
            parse_mode="HTML",
            reply_markup=get_profile_keyboard()
        )

    @bot.message_handler(func=lambda m: m.text == "❌ Отмена")
    async def handle_cancel(message: Message):
        user_id = message.from_user.id
        user_states.pop(user_id, None)
        await send_main_menu(bot, message.chat.id, user_id, "❌ Отменено")