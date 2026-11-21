from datetime import datetime, timedelta
from telebot import TeleBot
from telebot.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy import select, func, desc, or_
from sqlalchemy.orm import selectinload

from database import (
    User, Proxy, Order, Transaction, Setting, ProxyType, ProxyStatus, OrderStatus, TransactionType, UserRole,
    AsyncSessionLocal
)
from config import config
from keyboards import (
    get_admin_main_keyboard, get_admin_users_keyboard, get_admin_proxies_keyboard,
    get_admin_orders_keyboard, get_admin_finance_keyboard, get_admin_settings_keyboard,
    get_broadcast_confirm_keyboard, get_order_actions_keyboard, get_user_actions_keyboard,
    get_proxy_actions_keyboard, get_pagination_keyboard, get_cancel_keyboard,
    get_main_menu_keyboard,
)
from utils.states import AdminState, admin_states
from proxy.proxy6_client import proxy6_client, Proxy6Type, Proxy6Country


def is_admin(user_id: int) -> bool:
    return user_id in config.ADMIN_IDS


async def show_admin_main(bot: TeleBot, chat_id: int):
    """Show admin main menu"""
    async with AsyncSessionLocal() as session:
        # Quick stats
        users_count = await session.scalar(select(func.count(User.id)))
        active_users = await session.scalar(
            select(func.count(User.id)).where(User.is_banned == False)
        )
        orders_count = await session.scalar(select(func.count(Order.id)))
        pending_orders = await session.scalar(
            select(func.count(Order.id)).where(Order.status == OrderStatus.PENDING)
        )
        proxies_count = await session.scalar(select(func.count(Proxy.id)))
        available_proxies = await session.scalar(
            select(func.count(Proxy.id)).where(Proxy.status == ProxyStatus.AVAILABLE)
        )
        total_balance = await session.scalar(
            select(func.coalesce(func.sum(User.balance), 0))
        )
        today_deposits = await session.scalar(
            select(func.coalesce(func.sum(Transaction.amount), 0)).where(
                Transaction.type == TransactionType.DEPOSIT,
                Transaction.created_at >= datetime.utcnow().replace(hour=0, minute=0, second=0)
            )
        )

    text = (
        f"⚙️ <b>Админ-панель</b>\n\n"
        f"👥 Пользователей: {users_count} (активных: {active_users})\n"
        f"📋 Заказов: {orders_count} (ожидают: {pending_orders})\n"
        f"🔌 Прокси: {proxies_count} (доступно: {available_proxies})\n"
        f"💰 Общий баланс пользователей: {total_balance:.2f} ₽\n"
        f"📥 Пополнений за сегодня: {today_deposits:.2f} ₽\n\n"
        f"Выберите раздел:"
    )
    await bot.send_message(
        chat_id,
        text,
        parse_mode="HTML",
        reply_markup=get_admin_main_keyboard()
    )


def register_admin_handlers(bot: TeleBot):

    # --- Text handlers (Reply Keyboard) ---

    @bot.message_handler(func=lambda m: m.text == "📊 Статистика" and is_admin(m.from_user.id))
    async def admin_stats(message: Message):
        await show_admin_stats(bot, message.chat.id)

    @bot.message_handler(func=lambda m: m.text == "👥 Пользователи" and is_admin(m.from_user.id))
    async def admin_users(message: Message):
        await show_admin_users(bot, message.chat.id, page=0)

    @bot.message_handler(func=lambda m: m.text == "📦 Прокси" and is_admin(m.from_user.id))
    async def admin_proxies(message: Message):
        await show_admin_proxies_menu(bot, message.chat.id)

    @bot.message_handler(func=lambda m: m.text == "📋 Заказы" and is_admin(m.from_user.id))
    async def admin_orders(message: Message):
        await show_admin_orders_menu(bot, message.chat.id)

    @bot.message_handler(func=lambda m: m.text == "💰 Финансы" and is_admin(m.from_user.id))
    async def admin_finance(message: Message):
        await show_admin_finance_menu(bot, message.chat.id)

    @bot.message_handler(func=lambda m: m.text == "📢 Рассылка" and is_admin(m.from_user.id))
    async def admin_broadcast(message: Message):
        admin_states[message.from_user.id] = AdminState.BROADCAST_TEXT
        await bot.send_message(
            message.chat.id,
            "📢 <b>Рассылка</b>\n\nВведите текст сообщения для отправки всем пользователям:\n\n"
            "Поддерживается HTML разметка. Для отмены отправьте «❌ Отмена».",
            parse_mode="HTML",
            reply_markup=get_cancel_keyboard()
        )

    @bot.message_handler(func=lambda m: m.text == "⚙️ Настройки" and is_admin(m.from_user.id))
    async def admin_settings(message: Message):
        await show_admin_settings(bot, message.chat.id)

    @bot.message_handler(func=lambda m: m.text == "🔙 В главное меню" and is_admin(m.from_user.id))
    async def admin_back_to_main(message: Message):
        await send_main_menu(bot, message.chat.id, message.from_user.id, "🔙 Главное меню")

    # --- Callback handlers ---

    @bot.callback_query_handler(func=lambda c: c.data == "admin_main" and is_admin(c.from_user.id))
    async def cb_admin_main(callback: CallbackQuery):
        await show_admin_main(bot, callback.message.chat.id)

    @bot.callback_query_handler(func=lambda c: c.data == "admin_stats" and is_admin(c.from_user.id))
    async def cb_admin_stats(callback: CallbackQuery):
        await show_admin_stats(bot, callback.message.chat.id, callback.message.message_id)

    # Users
    @bot.callback_query_handler(func=lambda c: c.data.startswith("admin_users_page:") and is_admin(c.from_user.id))
    async def cb_admin_users_page(callback: CallbackQuery):
        page = int(callback.data.split(":")[1])
        await show_admin_users(bot, callback.message.chat.id, page, callback.message.message_id)

    @bot.callback_query_handler(func=lambda c: c.data == "admin_search_user" and is_admin(c.from_user.id))
    async def cb_admin_search_user(callback: CallbackQuery):
        admin_states[callback.from_user.id] = AdminState.SEARCH_USER
        await bot.edit_message_text(
            "🔍 Введите ID или username пользователя:",
            callback.message.chat.id,
            callback.message.message_id,
            reply_markup=InlineKeyboardMarkup().add(
                InlineKeyboardButton("❌ Отмена", callback_data="admin_users")
            )
        )

    @bot.callback_query_handler(func=lambda c: c.data == "admin_top_balance" and is_admin(c.from_user.id))
    async def cb_admin_top_balance(callback: CallbackQuery):
        await show_top_users(bot, callback.message.chat.id, "balance", callback.message.message_id)

    @bot.callback_query_handler(func=lambda c: c.data == "admin_top_orders" and is_admin(c.from_user.id))
    async def cb_admin_top_orders(callback: CallbackQuery):
        await show_top_users(bot, callback.message.chat.id, "orders", callback.message.message_id)

    @bot.callback_query_handler(func=lambda c: c.data.startswith("admin_view_user:") and is_admin(c.from_user.id))
    async def cb_admin_view_user(callback: CallbackQuery):
        user_id = int(callback.data.split(":")[1])
        await show_user_details(bot, callback.message.chat.id, user_id, callback.message.message_id)

    @bot.callback_query_handler(func=lambda c: c.data.startswith("admin_change_balance:") and is_admin(c.from_user.id))
    async def cb_admin_change_balance(callback: CallbackQuery):
        user_id = int(callback.data.split(":")[1])
        admin_states[callback.from_user.id] = AdminState.CHANGE_BALANCE
        admin_states[f"{callback.from_user.id}_target_user"] = user_id
        await bot.edit_message_text(
            f"💰 Введите сумму изменения баланса для пользователя {user_id}:\n"
            f"Положительное число — пополнение, отрицательное — списание.",
            callback.message.chat.id,
            callback.message.message_id,
            reply_markup=InlineKeyboardMarkup().add(
                InlineKeyboardButton("❌ Отмена", callback_data=f"admin_view_user:{user_id}")
            )
        )

    @bot.callback_query_handler(func=lambda c: c.data.startswith("admin_toggle_ban:") and is_admin(c.from_user.id))
    async def cb_admin_toggle_ban(callback: CallbackQuery):
        user_id = int(callback.data.split(":")[1])
        async with AsyncSessionLocal() as session:
            user = await session.get(User, user_id)
            if not user:
                await bot.answer_callback_query(callback.id, "Пользователь не найден")
                return
            if user.id in config.ADMIN_IDS:
                await bot.answer_callback_query(callback.id, "Нельзя заблокировать админа", show_alert=True)
                return
            user.is_banned = not user.is_banned
            await session.commit()
            status = "заблокирован" if user.is_banned else "разблокирован"
            await bot.answer_callback_query(callback.id, f"✅ Пользователь {status}")
            await show_user_details(bot, callback.message.chat.id, user_id, callback.message.message_id)

    @bot.callback_query_handler(func=lambda c: c.data.startswith("admin_user_orders:") and is_admin(c.from_user.id))
    async def cb_admin_user_orders(callback: CallbackQuery):
        user_id = int(callback.data.split(":")[1])
        await show_user_orders(bot, callback.message.chat.id, user_id, callback.message.message_id)

    @bot.callback_query_handler(func=lambda c: c.data.startswith("admin_user_proxies:") and is_admin(c.from_user.id))
    async def cb_admin_user_proxies(callback: CallbackQuery):
        user_id = int(callback.data.split(":")[1])
        await show_user_proxies(bot, callback.message.chat.id, user_id, callback.message.message_id)

    @bot.callback_query_handler(func=lambda c: c.data.startswith("admin_message_user:") and is_admin(c.from_user.id))
    async def cb_admin_message_user(callback: CallbackQuery):
        user_id = int(callback.data.split(":")[1])
        admin_states[callback.from_user.id] = AdminState.MESSAGE_USER
        admin_states[f"{callback.from_user.id}_target_user"] = user_id
        await bot.edit_message_text(
            f"💬 Введите сообщение для пользователя {user_id}:\n\n"
            f"Поддерживается HTML. Отмена — «❌ Отмена».",
            callback.message.chat.id,
            callback.message.message_id,
            reply_markup=InlineKeyboardMarkup().add(
                InlineKeyboardButton("❌ Отмена", callback_data=f"admin_view_user:{user_id}")
            )
        )

    # Proxies
    @bot.callback_query_handler(func=lambda c: c.data == "admin_proxies" and is_admin(c.from_user.id))
    async def cb_admin_proxies(callback: CallbackQuery):
        await show_admin_proxies_menu(bot, callback.message.chat.id, callback.message.message_id)

    @bot.callback_query_handler(func=lambda c: c.data.startswith("admin_all_proxies") and is_admin(c.from_user.id))
    async def cb_admin_all_proxies(callback: CallbackQuery):
        await show_admin_proxies_list(bot, callback.message.chat.id, page=0, message_id=callback.message.message_id)

    @bot.callback_query_handler(func=lambda c: c.data.startswith("admin_available_proxies") and is_admin(c.from_user.id))
    async def cb_admin_available_proxies(callback: CallbackQuery):
        await show_admin_proxies_list(bot, callback.message.chat.id, status=ProxyStatus.AVAILABLE, page=0, message_id=callback.message.message_id)

    @bot.callback_query_handler(func=lambda c: c.data.startswith("admin_sold_proxies") and is_admin(c.from_user.id))
    async def cb_admin_sold_proxies(callback: CallbackQuery):
        await show_admin_proxies_list(bot, callback.message.chat.id, status=ProxyStatus.SOLD, page=0, message_id=callback.message.message_id)

    @bot.callback_query_handler(func=lambda c: c.data.startswith("admin_pending_proxies") and is_admin(c.from_user.id))
    async def cb_admin_pending_proxies(callback: CallbackQuery):
        await show_admin_proxies_list(bot, callback.message.chat.id, status=ProxyStatus.PENDING, page=0, message_id=callback.message.message_id)

    @bot.callback_query_handler(func=lambda c: c.data.startswith("admin_proxies_page:") and is_admin(c.from_user.id))
    async def cb_admin_proxies_page(callback: CallbackQuery):
        parts = callback.data.split(":")
        page = int(parts[1])
        status = ProxyStatus(parts[2]) if len(parts) > 2 and parts[2] != "all" else None
        await show_admin_proxies_list(bot, callback.message.chat.id, status=status, page=page, message_id=callback.message.message_id)

    @bot.callback_query_handler(func=lambda c: c.data == "admin_add_proxy" and is_admin(c.from_user.id))
    async def cb_admin_add_proxy(callback: CallbackQuery):
        admin_states[callback.from_user.id] = AdminState.ADD_PROXY
        await bot.edit_message_text(
            "➕ <b>Добавление прокси вручную</b>\n\n"
            "Введите данные в формате:\n"
            "<code>тип|ip|port|login|password|страна|город|провайдер|цена_закупки|цена_продажи|дни_аренды</code>\n\n"
            "Пример:\n"
            "<code>socks5|1.2.3.4|1080|user|pass|ru|moscow|ISP|50|70|30</code>\n\n"
            "Поля login, password, город, провайдер можно оставить пустыми (||).",
            callback.message.chat.id,
            callback.message.message_id,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup().add(
                InlineKeyboardButton("❌ Отмена", callback_data="admin_proxies")
            )
        )

    @bot.callback_query_handler(func=lambda c: c.data == "admin_sync_proxies" and is_admin(c.from_user.id))
    async def cb_admin_sync_proxies(callback: CallbackQuery):
        await bot.edit_message_text(
            "🔄 Синхронизация с Proxy6.net...",
            callback.message.chat.id,
            callback.message.message_id,
        )
        try:
            await sync_proxies_from_api(bot, callback.message.chat.id)
        except Exception as e:
            await bot.edit_message_text(
                f"❌ Ошибка синхронизации: {e}",
                callback.message.chat.id,
                callback.message.message_id,
            )

    @bot.callback_query_handler(func=lambda c: c.data.startswith("admin_proxy_info:") and is_admin(c.from_user.id))
    async def cb_admin_proxy_info(callback: CallbackQuery):
        proxy_id = int(callback.data.split(":")[1])
        await show_admin_proxy_details(bot, callback.message.chat.id, proxy_id, callback.message.message_id)

    @bot.callback_query_handler(func=lambda c: c.data.startswith("admin_renew_proxy:") and is_admin(c.from_user.id))
    async def cb_admin_renew_proxy(callback: CallbackQuery):
        proxy_id = int(callback.data.split(":")[1])
        async with AsyncSessionLocal() as session:
            proxy = await session.get(Proxy, proxy_id)
            if not proxy or not proxy.proxy6_id:
                await bot.answer_callback_query(callback.id, "Прокси не найдено или нет ID у провайдера")
                return
            try:
                success = await proxy6_client.prolong_proxy(proxy.proxy6_id, 30)
                if success:
                    proxy.expires_at = (proxy.expires_at or datetime.utcnow()) + timedelta(days=30)
                    await session.commit()
                    await bot.answer_callback_query(callback.id, "✅ Продлено на 30 дней")
                else:
                    await bot.answer_callback_query(callback.id, "❌ Ошибка у провайдера")
            except Exception as e:
                await bot.answer_callback_query(callback.id, f"❌ Ошибка: {e}")

    @bot.callback_query_handler(func=lambda c: c.data.startswith("admin_change_ip:") and is_admin(c.from_user.id))
    async def cb_admin_change_ip(callback: CallbackQuery):
        proxy_id = int(callback.data.split(":")[1])
        async with AsyncSessionLocal() as session:
            proxy = await session.get(Proxy, proxy_id)
            if not proxy or not proxy.proxy6_id:
                await bot.answer_callback_query(callback.id, "Прокси не найдено или нет ID у провайдера")
                return
            try:
                new_proxy = await proxy6_client.change_ip(proxy.proxy6_id)
                if new_proxy:
                    proxy.ip = new_proxy.ip
                    proxy.port = new_proxy.port
                    proxy.login = new_proxy.user
                    proxy.password = new_proxy.password
                    proxy.date_end = new_proxy.date_end
                    await session.commit()
                    await bot.answer_callback_query(callback.id, "✅ IP изменен")
                    await show_admin_proxy_details(bot, callback.message.chat.id, proxy_id, callback.message.message_id)
                else:
                    await bot.answer_callback_query(callback.id, "❌ Не удалось сменить IP")
            except Exception as e:
                await bot.answer_callback_query(callback.id, f"❌ Ошибка: {e}")

    @bot.callback_query_handler(func=lambda c: c.data.startswith("admin_delete_proxy:") and is_admin(c.from_user.id))
    async def cb_admin_delete_proxy(callback: CallbackQuery):
        proxy_id = int(callback.data.split(":")[1])
        async with AsyncSessionLocal() as session:
            proxy = await session.get(Proxy, proxy_id)
            if not proxy:
                await bot.answer_callback_query(callback.id, "Прокси не найдено")
                return
            if proxy.proxy6_id:
                try:
                    await proxy6_client.delete_proxy(proxy.proxy6_id)
                except Exception:
                    pass
            proxy.status = ProxyStatus.EXPIRED
            proxy.user_id = None
            await session.commit()
            await bot.answer_callback_query(callback.id, "✅ Прокси удален")
            await show_admin_proxies_list(bot, callback.message.chat.id, page=0, message_id=callback.message.message_id)

    # Orders
    @bot.callback_query_handler(func=lambda c: c.data == "admin_orders" and is_admin(c.from_user.id))
    async def cb_admin_orders(callback: CallbackQuery):
        await show_admin_orders_menu(bot, callback.message.chat.id, callback.message.message_id)

    @bot.callback_query_handler(func=lambda c: c.data.startswith("admin_orders:") and is_admin(c.from_user.id))
    async def cb_admin_orders_status(callback: CallbackQuery):
        status_str = callback.data.split(":")[1]
        status = OrderStatus(status_str)
        await show_admin_orders_list(bot, callback.message.chat.id, status=status, page=0, message_id=callback.message.message_id)

    @bot.callback_query_handler(func=lambda c: c.data.startswith("admin_orders_page:") and is_admin(c.from_user.id))
    async def cb_admin_orders_page(callback: CallbackQuery):
        parts = callback.data.split(":")
        page = int(parts[1])
        status = OrderStatus(parts[2]) if len(parts) > 2 else None
        await show_admin_orders_list(bot, callback.message.chat.id, status=status, page=page, message_id=callback.message.message_id)

    @bot.callback_query_handler(func=lambda c: c.data.startswith("admin_order_info:") and is_admin(c.from_user.id))
    async def cb_admin_order_info(callback: CallbackQuery):
        order_id = int(callback.data.split(":")[1])
        await show_admin_order_details(bot, callback.message.chat.id, order_id, callback.message.message_id)

    @bot.callback_query_handler(func=lambda c: c.data.startswith("admin_confirm_order:") and is_admin(c.from_user.id))
    async def cb_admin_confirm_order(callback: CallbackQuery):
        order_id = int(callback.data.split(":")[1])
        async with AsyncSessionLocal() as session:
            order = await session.get(Order, order_id)
            if not order:
                await bot.answer_callback_query(callback.id, "Заказ не найден")
                return
            if order.status != OrderStatus.PENDING:
                await bot.answer_callback_query(callback.id, "Заказ не в ожидании")
                return
            # Check payment
            if order.yookassa_payment_id:
                from payments.yookassa_client import yookassa_client
                payment = yookassa_client.get_payment(order.yookassa_payment_id)
                if payment.status != "succeeded":
                    await bot.answer_callback_query(callback.id, f"Платеж не успешен: {payment.status}", show_alert=True)
                    return
            # Fulfill
            try:
                from handlers.user_handlers import fulfill_order
                await fulfill_order(bot, session, order)
                await bot.answer_callback_query(callback.id, "✅ Заказ выполнен")
            except Exception as e:
                await bot.answer_callback_query(callback.id, f"❌ Ошибка: {e}", show_alert=True)
            await show_admin_order_details(bot, callback.message.chat.id, order_id, callback.message.message_id)

    @bot.callback_query_handler(func=lambda c: c.data.startswith("admin_cancel_order:") and is_admin(c.from_user.id))
    async def cb_admin_cancel_order(callback: CallbackQuery):
        order_id = int(callback.data.split(":")[1])
        async with AsyncSessionLocal() as session:
            order = await session.get(Order, order_id)
            if not order:
                await bot.answer_callback_query(callback.id, "Заказ не найден")
                return
            order.status = OrderStatus.FAILED
            await session.commit()
            await bot.answer_callback_query(callback.id, "✅ Заказ отменен")
            await show_admin_order_details(bot, callback.message.chat.id, order_id, callback.message.message_id)

    @bot.callback_query_handler(func=lambda c: c.data.startswith("admin_fulfill_order:") and is_admin(c.from_user.id))
    async def cb_admin_fulfill_order(callback: CallbackQuery):
        order_id = int(callback.data.split(":")[1])
        async with AsyncSessionLocal() as session:
            order = await session.get(Order, order_id)
            if not order:
                await bot.answer_callback_query(callback.id, "Заказ не найден")
                return
            try:
                from handlers.user_handlers import fulfill_order
                await fulfill_order(bot, session, order)
                await bot.answer_callback_query(callback.id, "✅ Прокси выданы")
            except Exception as e:
                await bot.answer_callback_query(callback.id, f"❌ Ошибка: {e}", show_alert=True)
            await show_admin_order_details(bot, callback.message.chat.id, order_id, callback.message.message_id)

    @bot.callback_query_handler(func=lambda c: c.data.startswith("admin_refund_order:") and is_admin(c.from_user.id))
    async def cb_admin_refund_order(callback: CallbackQuery):
        order_id = int(callback.data.split(":")[1])
        async with AsyncSessionLocal() as session:
            order = await session.get(Order, order_id)
            if not order:
                await bot.answer_callback_query(callback.id, "Заказ не найден")
                return
            if order.status not in [OrderStatus.PAID, OrderStatus.COMPLETED]:
                await bot.answer_callback_query(callback.id, "Можно вернуть только оплаченные заказы", show_alert=True)
                return
            if not order.yookassa_payment_id:
                await bot.answer_callback_query(callback.id, "Нет ID платежа", show_alert=True)
                return
            try:
                from payments.yookassa_client import yookassa_client
                yookassa_client.cancel_payment(order.yookassa_payment_id)
                order.status = OrderStatus.REFUNDED
                # Return money to user
                user = await session.get(User, order.user_id)
                if user:
                    user.balance += order.total_price
                    session.add(Transaction(
                        user_id=user.id,
                        type=TransactionType.REFUND,
                        amount=order.total_price,
                        balance_before=user.balance - order.total_price,
                        balance_after=user.balance,
                        description=f"Возврат за заказ #{order.id}",
                        order_id=order.id,
                    ))
                await session.commit()
                await bot.answer_callback_query(callback.id, "✅ Возврат обработан")
            except Exception as e:
                await bot.answer_callback_query(callback.id, f"❌ Ошибка: {e}", show_alert=True)
            await show_admin_order_details(bot, callback.message.chat.id, order_id, callback.message.message_id)

    # Finance
    @bot.callback_query_handler(func=lambda c: c.data == "admin_finance" and is_admin(c.from_user.id))
    async def cb_admin_finance(callback: CallbackQuery):
        await show_admin_finance_menu(bot, callback.message.chat.id, callback.message.message_id)

    @bot.callback_query_handler(func=lambda c: c.data == "admin_bot_balance" and is_admin(c.from_user.id))
    async def cb_admin_bot_balance(callback: CallbackQuery):
        async with AsyncSessionLocal() as session:
            total_balance = await session.scalar(select(func.coalesce(func.sum(User.balance), 0)))
            today_income = await session.scalar(
                select(func.coalesce(func.sum(Transaction.amount), 0)).where(
                    Transaction.type == TransactionType.DEPOSIT,
                    Transaction.created_at >= datetime.utcnow().replace(hour=0, minute=0, second=0)
                )
            )
            today_outcome = await session.scalar(
                select(func.coalesce(func.sum(Transaction.amount), 0)).where(
                    Transaction.type == TransactionType.PURCHASE,
                    Transaction.created_at >= datetime.utcnow().replace(hour=0, minute=0, second=0)
                )
            )
        await bot.edit_message_text(
            f"💰 <b>Баланс бота</b>\n\n"
            f"👥 Баланс пользователей: {total_balance:.2f} ₽\n"
            f"📥 Пополнений за сегодня: {today_income:.2f} ₽\n"
            f"📤 Покупок за сегодня: {abs(today_outcome):.2f} ₽\n"
            f"📊 Чистая прибыль за день: {(today_income + today_outcome):.2f} ₽",
            callback.message.chat.id,
            callback.message.message_id,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup().add(
                InlineKeyboardButton("🔙 Назад", callback_data="admin_finance")
            )
        )

    @bot.callback_query_handler(func=lambda c: c.data == "admin_deposits" and is_admin(c.from_user.id))
    async def cb_admin_deposits(callback: CallbackQuery):
        await show_recent_transactions(bot, callback.message.chat.id, TransactionType.DEPOSIT, callback.message.message_id)

    @bot.callback_query_handler(func=lambda c: c.data == "admin_withdrawals" and is_admin(c.from_user.id))
    async def cb_admin_withdrawals(callback: CallbackQuery):
        await show_recent_transactions(bot, callback.message.chat.id, TransactionType.PURCHASE, callback.message.message_id)

    @bot.callback_query_handler(func=lambda c: c.data.startswith("admin_report_") and is_admin(c.from_user.id))
    async def cb_admin_report(callback: CallbackQuery):
        period = callback.data.split("_")[2]  # day, week, month
        await show_finance_report(bot, callback.message.chat.id, period, callback.message.message_id)

    # Settings
    @bot.callback_query_handler(func=lambda c: c.data == "admin_settings" and is_admin(c.from_user.id))
    async def cb_admin_settings(callback: CallbackQuery):
        await show_admin_settings(bot, callback.message.chat.id, callback.message.message_id)

    @bot.callback_query_handler(func=lambda c: c.data == "admin_set_min_deposit" and is_admin(c.from_user.id))
    async def cb_admin_set_min_deposit(callback: CallbackQuery):
        admin_states[callback.from_user.id] = AdminState.SET_MIN_DEPOSIT
        await bot.edit_message_text(
            f"💲 Текущее минимальное пополнение: {config.MIN_DEPOSIT} ₽\n\nВведите новое значение:",
            callback.message.chat.id,
            callback.message.message_id,
            reply_markup=InlineKeyboardMarkup().add(
                InlineKeyboardButton("❌ Отмена", callback_data="admin_settings")
            )
        )

    @bot.callback_query_handler(func=lambda c: c.data == "admin_set_ref_bonus" and is_admin(c.from_user.id))
    async def cb_admin_set_ref_bonus(callback: CallbackQuery):
        admin_states[callback.from_user.id] = AdminState.SET_REF_BONUS
        await bot.edit_message_text(
            f"🎁 Текущий реферальный бонус: {config.REFERRAL_BONUS} ₽\n\nВведите новое значение:",
            callback.message.chat.id,
            callback.message.message_id,
            reply_markup=InlineKeyboardMarkup().add(
                InlineKeyboardButton("❌ Отмена", callback_data="admin_settings")
            )
        )

    @bot.callback_query_handler(func=lambda c: c.data == "admin_set_markup" and is_admin(c.from_user.id))
    async def cb_admin_set_markup(callback: CallbackQuery):
        admin_states[callback.from_user.id] = AdminState.SET_MARKUP
        await bot.edit_message_text(
            f"📈 Текущая наценка: {config.PROXY_MARKUP_PERCENT * 100:.0f}%\n\nВведите новое значение в процентах (например, 20):",
            callback.message.chat.id,
            callback.message.message_id,
            reply_markup=InlineKeyboardMarkup().add(
                InlineKeyboardButton("❌ Отмена", callback_data="admin_settings")
            )
        )

    @bot.callback_query_handler(func=lambda c: c.data == "admin_maintenance" and is_admin(c.from_user.id))
    async def cb_admin_maintenance(callback: CallbackQuery):
        # Toggle maintenance mode
        async with AsyncSessionLocal() as session:
            setting = await session.get(Setting, "maintenance_mode")
            if not setting:
                setting = Setting(key="maintenance_mode", value="false", description="Technical maintenance mode")
                session.add(setting)
            setting.value = "true" if setting.value == "false" else "false"
            await session.commit()
            mode = "включен" if setting.value == "true" else "выключен"
            await bot.answer_callback_query(callback.id, f"🔧 Тех. работы {mode}")
            await show_admin_settings(bot, callback.message.chat.id, callback.message.message_id)

    # Broadcast
    @bot.callback_query_handler(func=lambda c: c.data == "broadcast_confirm" and is_admin(c.from_user.id))
    async def cb_broadcast_confirm(callback: CallbackQuery):
        text = admin_states.get(f"{callback.from_user.id}_broadcast_text")
        if not text:
            await bot.answer_callback_query(callback.id, "Текст не найден")
            return
        await bot.edit_message_text(
            "📢 Рассылка запущена...",
            callback.message.chat.id,
            callback.message.message_id,
        )
        sent, failed = await send_broadcast(bot, text)
        await bot.edit_message_text(
            f"✅ Рассылка завершена\n\n"
            f"📤 Отправлено: {sent}\n"
            f"❌ Ошибок: {failed}",
            callback.message.chat.id,
            callback.message.message_id,
            reply_markup=InlineKeyboardMarkup().add(
                InlineKeyboardButton("🔙 Назад", callback_data="admin_main")
            )
        )
        admin_states.pop(callback.from_user.id, None)
        admin_states.pop(f"{callback.from_user.id}_broadcast_text", None)

    @bot.callback_query_handler(func=lambda c: c.data == "broadcast_cancel" and is_admin(c.from_user.id))
    async def cb_broadcast_cancel(callback: CallbackQuery):
        admin_states.pop(callback.from_user.id, None)
        admin_states.pop(f"{callback.from_user.id}_broadcast_text", None)
        await bot.edit_message_text(
            "❌ Рассылка отменена",
            callback.message.chat.id,
            callback.message.message_id,
            reply_markup=InlineKeyboardMarkup().add(
                InlineKeyboardButton("🔙 Назад", callback_data="admin_main")
            )
        )


# --- Helper functions ---

async def show_admin_stats(bot: TeleBot, chat_id: int, message_id: int = None):
    async with AsyncSessionLocal() as session:
        users_total = await session.scalar(select(func.count(User.id)))
        users_active = await session.scalar(select(func.count(User.id)).where(User.is_banned == False))
        users_banned = await session.scalar(select(func.count(User.id)).where(User.is_banned == True))
        users_with_balance = await session.scalar(select(func.count(User.id)).where(User.balance > 0))

        orders_total = await session.scalar(select(func.count(Order.id)))
        orders_pending = await session.scalar(select(func.count(Order.id)).where(Order.status == OrderStatus.PENDING))
        orders_paid = await session.scalar(select(func.count(Order.id)).where(Order.status == OrderStatus.PAID))
        orders_completed = await session.scalar(select(func.count(Order.id)).where(Order.status == OrderStatus.COMPLETED))
        orders_failed = await session.scalar(select(func.count(Order.id)).where(Order.status == OrderStatus.FAILED))

        proxies_total = await session.scalar(select(func.count(Proxy.id)))
        proxies_available = await session.scalar(select(func.count(Proxy.id)).where(Proxy.status == ProxyStatus.AVAILABLE))
        proxies_sold = await session.scalar(select(func.count(Proxy.id)).where(Proxy.status == ProxyStatus.SOLD))

        total_revenue = await session.scalar(
            select(func.coalesce(func.sum(Transaction.amount), 0)).where(Transaction.amount > 0)
        )
        total_spent = await session.scalar(
            select(func.coalesce(func.sum(Transaction.amount), 0)).where(Transaction.amount < 0)
        )

        today = datetime.utcnow().replace(hour=0, minute=0, second=0)
        users_today = await session.scalar(select(func.count(User.id)).where(User.created_at >= today))
        orders_today = await session.scalar(select(func.count(Order.id)).where(Order.created_at >= today))
        revenue_today = await session.scalar(
            select(func.coalesce(func.sum(Transaction.amount), 0)).where(
                Transaction.amount > 0, Transaction.created_at >= today
            )
        )

    text = (
        f"📊 <b>Статистика</b>\n\n"
        f"👥 <b>Пользователи:</b>\n"
        f"  Всего: {users_total}\n"
        f"  Активных: {users_active}\n"
        f"  Заблокированных: {users_banned}\n"
        f"  С балансом > 0: {users_with_balance}\n"
        f"  Новых за сегодня: {users_today}\n\n"
        f"📋 <b>Заказы:</b>\n"
        f"  Всего: {orders_total}\n"
        f"  Ожидают оплаты: {orders_pending}\n"
        f"  Оплачены: {orders_paid}\n"
        f"  Выполнены: {orders_completed}\n"
        f"  Отменены: {orders_failed}\n"
        f"  За сегодня: {orders_today}\n\n"
        f"🔌 <b>Прокси:</b>\n"
        f"  Всего: {proxies_total}\n"
        f"  Доступно: {proxies_available}\n"
        f"  Продано: {proxies_sold}\n\n"
        f"💰 <b>Финансы:</b>\n"
        f"  Общий доход: {total_revenue:.2f} ₽\n"
        f"  Общие расходы: {abs(total_spent):.2f} ₽\n"
        f"  Прибыль: {(total_revenue + total_spent):.2f} ₽\n"
        f"  Доход за сегодня: {revenue_today:.2f} ₽"
    )

    kb = InlineKeyboardMarkup().add(InlineKeyboardButton("🔙 Назад", callback_data="admin_main"))

    if message_id:
        await bot.edit_message_text(text, chat_id, message_id, parse_mode="HTML", reply_markup=kb)
    else:
        await bot.send_message(chat_id, text, parse_mode="HTML", reply_markup=kb)


async def show_admin_users(bot: TeleBot, chat_id: int, page: int = 0, message_id: int = None):
    per_page = 10
    async with AsyncSessionLocal() as session:
        users = await session.scalars(
            select(User)
            .order_by(desc(User.created_at))
            .limit(per_page)
            .offset(page * per_page)
        )
        users = list(users)
        total = await session.scalar(select(func.count(User.id)))

    if not users:
        text = "👥 Пользователей не найдено"
    else:
        text = f"👥 <b>Пользователи (стр. {page+1}/{(total-1)//per_page+1})</b>:\n\n"
        for u in users:
            status = "🚫" if u.is_banned else "✅"
            text += (
                f"{status} <b>{u.id}</b> | @{u.username or '—'} | "
                f"{u.first_name or ''} {u.last_name or ''}\n"
                f"  💰 {u.balance:.2f} ₽ | 📦 {len(u.orders) if u.orders else 0} заказов | "
                f"📅 {u.created_at.strftime('%d.%m.%Y')}\n\n"
            )

    total_pages = (total - 1) // per_page + 1
    kb = get_pagination_keyboard(page, total_pages, "admin_users")

    if message_id:
        await bot.edit_message_text(text, chat_id, message_id, parse_mode="HTML", reply_markup=kb)
    else:
        await bot.send_message(chat_id, text, parse_mode="HTML", reply_markup=kb)


async def show_top_users(bot: TeleBot, chat_id: int, sort_by: str, message_id: int = None):
    async with AsyncSessionLocal() as session:
        if sort_by == "balance":
            users = await session.scalars(
                select(User)
                .order_by(desc(User.balance))
                .limit(10)
            )
            title = "💰 Топ по балансу"
        else:
            users = await session.scalars(
                select(User)
                .join(Order, User.id == Order.user_id, isouter=True)
                .group_by(User.id)
                .order_by(desc(func.count(Order.id)))
                .limit(10)
            )
            title = "📦 Топ по заказам"
        users = list(users)

    text = f"{title}:\n\n"
    for i, u in enumerate(users, 1):
        val = u.balance if sort_by == "balance" else len(u.orders) if u.orders else 0
        text += f"{i}. <b>{u.id}</b> @{u.username or '—'} — {val}\n"

    kb = InlineKeyboardMarkup().add(InlineKeyboardButton("🔙 Назад", callback_data="admin_users"))

    if message_id:
        await bot.edit_message_text(text, chat_id, message_id, parse_mode="HTML", reply_markup=kb)
    else:
        await bot.send_message(chat_id, text, parse_mode="HTML", reply_markup=kb)


async def show_user_details(bot: TeleBot, chat_id: int, user_id: int, message_id: int = None):
    async with AsyncSessionLocal() as session:
        user = await session.get(User, user_id)
        if not user:
            text = "Пользователь не найден"
            kb = InlineKeyboardMarkup().add(InlineKeyboardButton("🔙 Назад", callback_data="admin_users"))
            if message_id:
                await bot.edit_message_text(text, chat_id, message_id, reply_markup=kb)
            else:
                await bot.send_message(chat_id, text, reply_markup=kb)
            return

        orders_count = len(user.orders) if user.orders else 0
        proxies_count = len(user.proxies) if user.proxies else 0
        refs_count = await session.scalar(select(func.count(User.id)).where(User.referred_by == user.id))
        ref_earnings = await session.scalar(
            select(func.coalesce(func.sum(Transaction.amount), 0)).where(
                Transaction.user_id == user.id, Transaction.type == TransactionType.REFERRAL
            )
        )
        total_spent = await session.scalar(
            select(func.coalesce(func.sum(Transaction.amount), 0)).where(
                Transaction.user_id == user.id, Transaction.type == TransactionType.PURCHASE
            )
        )
        total_deposited = await session.scalar(
            select(func.coalesce(func.sum(Transaction.amount), 0)).where(
                Transaction.user_id == user.id, Transaction.type == TransactionType.DEPOSIT
            )
        )

    text = (
        f"👤 <b>Пользователь {user.id}</b>\n\n"
        f"👤 Имя: {user.first_name or ''} {user.last_name or ''}\n"
        f"🔗 Username: @{user.username or '—'}\n"
        f"💰 Баланс: {user.balance:.2f} ₽\n"
        f"📦 Заказов: {orders_count}\n"
        f"🔌 Прокси: {proxies_count}\n"
        f"🎁 Рефералов: {refs_count} (заработано: {ref_earnings:.2f} ₽)\n"
        f"📥 Пополнено: {total_deposited:.2f} ₽\n"
        f"📤 Потрачено: {abs(total_spent):.2f} ₽\n"
        f"🚫 Заблокирован: {'Да' if user.is_banned else 'Нет'}\n"
        f"📅 Регистрация: {user.created_at.strftime('%d.%m.%Y %H:%M')}\n"
        f"🔑 Реф. код: {user.referral_code}"
    )

    kb = get_user_actions_keyboard(user.id)

    if message_id:
        await bot.edit_message_text(text, chat_id, message_id, parse_mode="HTML", reply_markup=kb)
    else:
        await bot.send_message(chat_id, text, parse_mode="HTML", reply_markup=kb)


async def show_user_orders(bot: TeleBot, chat_id: int, user_id: int, message_id: int = None):
    async with AsyncSessionLocal() as session:
        orders = await session.scalars(
            select(Order)
            .where(Order.user_id == user_id)
            .order_by(desc(Order.created_at))
            .limit(20)
        )
        orders = list(orders)

    if not orders:
        text = "Заказов нет"
    else:
        text = f"📋 <b>Заказы пользователя {user_id}</b>:\n\n"
        for o in orders:
            status_emoji = {
                OrderStatus.PENDING: "⏳",
                OrderStatus.PAID: "✅",
                OrderStatus.COMPLETED: "📦",
                OrderStatus.FAILED: "❌",
                OrderStatus.REFUNDED: "💸",
            }.get(o.status, "❓")
            text += (
                f"{status_emoji} <b>#{o.id}</b> {o.proxy_type.value.upper()} x{o.count} "
                f"({o.country.upper()}) {o.period_days}д. — {o.total_price:.2f} ₽\n"
                f"   {o.created_at.strftime('%d.%m.%Y %H:%M')}\n\n"
            )

    kb = InlineKeyboardMarkup().add(InlineKeyboardButton("🔙 Назад", callback_data=f"admin_view_user:{user_id}"))

    if message_id:
        await bot.edit_message_text(text, chat_id, message_id, parse_mode="HTML", reply_markup=kb)
    else:
        await bot.send_message(chat_id, text, parse_mode="HTML", reply_markup=kb)


async def show_user_proxies(bot: TeleBot, chat_id: int, user_id: int, message_id: int = None):
    async with AsyncSessionLocal() as session:
        proxies = await session.scalars(
            select(Proxy)
            .where(Proxy.user_id == user_id)
            .order_by(desc(Proxy.created_at))
            .limit(20)
        )
        proxies = list(proxies)

    if not proxies:
        text = "Прокси нет"
    else:
        text = f"🔌 <b>Прокси пользователя {user_id}</b>:\n\n"
        for p in proxies:
            status_emoji = "✅" if p.status == ProxyStatus.SOLD else "⏳"
            text += (
                f"{status_emoji} {p.ip}:{p.port} ({p.type.value.upper()}) "
                f"{p.country or ''} — до {p.expires_at.strftime('%d.%m.%Y') if p.expires_at else '?'}\n"
            )

    kb = InlineKeyboardMarkup().add(InlineKeyboardButton("🔙 Назад", callback_data=f"admin_view_user:{user_id}"))

    if message_id:
        await bot.edit_message_text(text, chat_id, message_id, parse_mode="HTML", reply_markup=kb)
    else:
        await bot.send_message(chat_id, text, parse_mode="HTML", reply_markup=kb)


async def show_admin_proxies_menu(bot: TeleBot, chat_id: int, message_id: int = None):
    async with AsyncSessionLocal() as session:
        total = await session.scalar(select(func.count(Proxy.id)))
        available = await session.scalar(select(func.count(Proxy.id)).where(Proxy.status == ProxyStatus.AVAILABLE))
        sold = await session.scalar(select(func.count(Proxy.id)).where(Proxy.status == ProxyStatus.SOLD))
        pending = await session.scalar(select(func.count(Proxy.id)).where(Proxy.status == ProxyStatus.PENDING))

    text = (
        f"📦 <b>Управление прокси</b>\n\n"
        f"Всего: {total}\n"
        f"✅ Доступно: {available}\n"
        f"🛒 Продано: {sold}\n"
        f"⏳ Ожидает: {pending}\n\n"
        f"Выберите действие:"
    )

    if message_id:
        await bot.edit_message_text(text, chat_id, message_id, parse_mode="HTML", reply_markup=get_admin_proxies_keyboard())
    else:
        await bot.send_message(chat_id, text, parse_mode="HTML", reply_markup=get_admin_proxies_keyboard())


async def show_admin_proxies_list(bot: TeleBot, chat_id: int, status: ProxyStatus = None, page: int = 0, message_id: int = None):
    per_page = 10
    async with AsyncSessionLocal() as session:
        query = select(Proxy).order_by(desc(Proxy.created_at))
        if status:
            query = query.where(Proxy.status == status)
        proxies = await session.scalars(query.limit(per_page).offset(page * per_page))
        proxies = list(proxies)

        count_query = select(func.count(Proxy.id))
        if status:
            count_query = count_query.where(Proxy.status == status)
        total = await session.scalar(count_query)

    if not proxies:
        text = "Прокси не найдены"
    else:
        status_text = f" ({status.value})" if status else ""
        text = f"📦 <b>Прокси{status_text} (стр. {page+1}/{(total-1)//per_page+1})</b>:\n\n"
        for p in proxies:
            status_emoji = {
                ProxyStatus.AVAILABLE: "🟢",
                ProxyStatus.SOLD: "✅",
                ProxyStatus.EXPIRED: "🔴",
                ProxyStatus.PENDING: "🟡",
            }.get(p.status, "⚪")
            user_info = f" @{p.user.username}" if p.user else ""
            text += (
                f"{status_emoji} <b>#{p.id}</b> {p.ip}:{p.port} ({p.type.value.upper()}) "
                f"{p.country or ''}{user_info}\n"
                f"  💰 {p.sale_price:.2f}₽ | 📅 {p.expires_at.strftime('%d.%m') if p.expires_at else '?'}\n\n"
            )

    total_pages = (total - 1) // per_page + 1
    prefix = f"admin_proxies_{status.value}" if status else "admin_proxies_all"
    kb = get_pagination_keyboard(page, total_pages, prefix)
    # Add proxy info buttons
    for p in proxies:
        kb.add(InlineKeyboardButton(f"ℹ️ #{p.id}", callback_data=f"admin_proxy_info:{p.id}"))

    if message_id:
        await bot.edit_message_text(text, chat_id, message_id, parse_mode="HTML", reply_markup=kb)
    else:
        await bot.send_message(chat_id, text, parse_mode="HTML", reply_markup=kb)


async def show_admin_proxy_details(bot: TeleBot, chat_id: int, proxy_id: int, message_id: int = None):
    async with AsyncSessionLocal() as session:
        proxy = await session.get(Proxy, proxy_id)
        if not proxy:
            text = "Прокси не найдено"
            kb = InlineKeyboardMarkup().add(InlineKeyboardButton("🔙 Назад", callback_data="admin_proxies"))
            if message_id:
                await bot.edit_message_text(text, chat_id, message_id, reply_markup=kb)
            else:
                await bot.send_message(chat_id, text, reply_markup=kb)
            return

    text = format_proxy_info(proxy)
    if proxy.user:
        text += f"\n👤 Владелец: {proxy.user.id} @{proxy.user.username or '—'}"
    if proxy.order:
        text += f"\n📋 Заказ: #{proxy.order.id}"

    kb = get_proxy_actions_keyboard(proxy.id)

    if message_id:
        await bot.edit_message_text(text, chat_id, message_id, parse_mode="HTML", reply_markup=kb)
    else:
        await bot.send_message(chat_id, text, parse_mode="HTML", reply_markup=kb)


async def show_admin_orders_menu(bot: TeleBot, chat_id: int, message_id: int = None):
    async with AsyncSessionLocal() as session:
        pending = await session.scalar(select(func.count(Order.id)).where(Order.status == OrderStatus.PENDING))
        paid = await session.scalar(select(func.count(Order.id)).where(Order.status == OrderStatus.PAID))
        completed = await session.scalar(select(func.count(Order.id)).where(Order.status == OrderStatus.COMPLETED))
        failed = await session.scalar(select(func.count(Order.id)).where(Order.status == OrderStatus.FAILED))

    text = (
        f"📋 <b>Управление заказами</b>\n\n"
        f"⏳ Ожидают оплаты: {pending}\n"
        f"✅ Оплачены: {paid}\n"
        f"📦 Выполнены: {completed}\n"
        f"❌ Отменены: {failed}\n\n"
        f"Выберите статус:"
    )

    if message_id:
        await bot.edit_message_text(text, chat_id, message_id, parse_mode="HTML", reply_markup=get_admin_orders_keyboard())
    else:
        await bot.send_message(chat_id, text, parse_mode="HTML", reply_markup=get_admin_orders_keyboard())


async def show_admin_orders_list(bot: TeleBot, chat_id: int, status: OrderStatus = None, page: int = 0, message_id: int = None):
    per_page = 10
    async with AsyncSessionLocal() as session:
        query = select(Order).options(selectinload(Order.user)).order_by(desc(Order.created_at))
        if status:
            query = query.where(Order.status == status)
        orders = await session.scalars(query.limit(per_page).offset(page * per_page))
        orders = list(orders)

        count_query = select(func.count(Order.id))
        if status:
            count_query = count_query.where(Order.status == status)
        total = await session.scalar(count_query)

    if not orders:
        text = "Заказов не найдено"
    else:
        status_text = f" ({status.value})" if status else ""
        text = f"📋 <b>Заказы{status_text} (стр. {page+1}/{(total-1)//per_page+1})</b>:\n\n"
        for o in orders:
            status_emoji = {
                OrderStatus.PENDING: "⏳",
                OrderStatus.PAID: "✅",
                OrderStatus.COMPLETED: "📦",
                OrderStatus.FAILED: "❌",
                OrderStatus.REFUNDED: "💸",
            }.get(o.status, "❓")
            text += (
                f"{status_emoji} <b>#{o.id}</b> {o.user.id} @{o.user.username or '—'}\n"
                f"  {o.proxy_type.value.upper()} x{o.count} ({o.country.upper()}) {o.period_days}д. — {o.total_price:.2f} ₽\n"
                f"  {o.created_at.strftime('%d.%m.%Y %H:%M')}\n\n"
            )

    total_pages = (total - 1) // per_page + 1
    prefix = f"admin_orders_{status.value}" if status else "admin_orders_all"
    kb = get_pagination_keyboard(page, total_pages, prefix)
    for o in orders:
        kb.add(InlineKeyboardButton(f"ℹ️ #{o.id}", callback_data=f"admin_order_info:{o.id}"))

    if message_id:
        await bot.edit_message_text(text, chat_id, message_id, parse_mode="HTML", reply_markup=kb)
    else:
        await bot.send_message(chat_id, text, parse_mode="HTML", reply_markup=kb)


async def show_admin_order_details(bot: TeleBot, chat_id: int, order_id: int, message_id: int = None):
    async with AsyncSessionLocal() as session:
        order = await session.get(Order, order_id, options=[selectinload(Order.user), selectinload(Order.proxies)])
        if not order:
            text = "Заказ не найден"
            kb = InlineKeyboardMarkup().add(InlineKeyboardButton("🔙 Назад", callback_data="admin_orders"))
            if message_id:
                await bot.edit_message_text(text, chat_id, message_id, reply_markup=kb)
            else:
                await bot.send_message(chat_id, text, reply_markup=kb)
            return

    status_emoji = {
        OrderStatus.PENDING: "⏳",
        OrderStatus.PAID: "✅",
        OrderStatus.COMPLETED: "📦",
        OrderStatus.FAILED: "❌",
        OrderStatus.REFUNDED: "💸",
    }.get(order.status, "❓")

    text = (
        f"{status_emoji} <b>Заказ #{order.id}</b>\n\n"
        f"👤 Пользователь: {order.user.id} @{order.user.username or '—'}\n"
        f"🌐 Тип: {order.proxy_type.value.upper()}\n"
        f"🌍 Страна: {order.country.upper()}\n"
        f"🔢 Количество: {order.count}\n"
        f"📅 Срок: {order.period_days} дней\n"
        f"💰 Сумма: {order.total_price:.2f} ₽\n"
        f"📊 Статус: {order.status.value}\n"
        f"📅 Создан: {order.created_at.strftime('%d.%m.%Y %H:%M')}\n"
    )
    if order.yookassa_payment_id:
        text += f"💳 Payment ID: {order.yookassa_payment_id}\n"
    if order.completed_at:
        text += f"✅ Выполнен: {order.completed_at.strftime('%d.%m.%Y %H:%M')}\n"

    if order.proxies:
        text += "\n🔌 <b>Прокси:</b>\n"
        for p in order.proxies:
            text += f"  {p.ip}:{p.port} ({p.type.value.upper()})\n"

    kb = get_order_actions_keyboard(order.id, order.status)

    if message_id:
        await bot.edit_message_text(text, chat_id, message_id, parse_mode="HTML", reply_markup=kb)
    else:
        await bot.send_message(chat_id, text, parse_mode="HTML", reply_markup=kb)


async def show_admin_finance_menu(bot: TeleBot, chat_id: int, message_id: int = None):
    async with AsyncSessionLocal() as session:
        total_balance = await session.scalar(select(func.coalesce(func.sum(User.balance), 0)))
        today = datetime.utcnow().replace(hour=0, minute=0, second=0)
        today_deposits = await session.scalar(
            select(func.coalesce(func.sum(Transaction.amount), 0)).where(
                Transaction.type == TransactionType.DEPOSIT, Transaction.created_at >= today
            )
        )
        today_purchases = await session.scalar(
            select(func.coalesce(func.sum(Transaction.amount), 0)).where(
                Transaction.type == TransactionType.PURCHASE, Transaction.created_at >= today
            )
        )

    text = (
        f"💰 <b>Финансы</b>\n\n"
        f"💵 Баланс пользователей: {total_balance:.2f} ₽\n"
        f"📥 Пополнений за сегодня: {today_deposits:.2f} ₽\n"
        f"📤 Покупок за сегодня: {abs(today_purchases):.2f} ₽\n"
        f"📊 Прибыль за день: {(today_deposits + today_purchases):.2f} ₽\n\n"
        f"Выберите раздел:"
    )

    if message_id:
        await bot.edit_message_text(text, chat_id, message_id, parse_mode="HTML", reply_markup=get_admin_finance_keyboard())
    else:
        await bot.send_message(chat_id, text, parse_mode="HTML", reply_markup=get_admin_finance_keyboard())


async def show_recent_transactions(bot: TeleBot, chat_id: int, txn_type: TransactionType, message_id: int = None):
    async with AsyncSessionLocal() as session:
        txns = await session.scalars(
            select(Transaction)
            .options(selectinload(Transaction.user))
            .where(Transaction.type == txn_type)
            .order_by(desc(Transaction.created_at))
            .limit(20)
        )
        txns = list(txns)

    type_name = "Пополнения" if txn_type == TransactionType.DEPOSIT else "Покупки"
    text = f"💳 <b>{type_name} (последние 20)</b>:\n\n"
    for t in txns:
        sign = "+" if t.amount > 0 else ""
        text += (
            f"{sign}{t.amount:.2f} ₽ | {t.user.id} @{t.user.username or '—'}\n"
            f"  {t.description or '—'}\n"
            f"  {t.created_at.strftime('%d.%m.%Y %H:%M')}\n\n"
        )

    kb = InlineKeyboardMarkup().add(InlineKeyboardButton("🔙 Назад", callback_data="admin_finance"))

    if message_id:
        await bot.edit_message_text(text, chat_id, message_id, parse_mode="HTML", reply_markup=kb)
    else:
        await bot.send_message(chat_id, text, parse_mode="HTML", reply_markup=kb)


async def show_finance_report(bot: TeleBot, chat_id: int, period: str, message_id: int = None):
    now = datetime.utcnow()
    if period == "day":
        start = now.replace(hour=0, minute=0, second=0)
        label = "день"
    elif period == "week":
        start = now - timedelta(days=7)
        label = "неделю"
    else:
        start = now.replace(day=1, hour=0, minute=0, second=0)
        label = "месяц"

    async with AsyncSessionLocal() as session:
        deposits = await session.scalar(
            select(func.coalesce(func.sum(Transaction.amount), 0)).where(
                Transaction.type == TransactionType.DEPOSIT, Transaction.created_at >= start
            )
        )
        purchases = await session.scalar(
            select(func.coalesce(func.sum(Transaction.amount), 0)).where(
                Transaction.type == TransactionType.PURCHASE, Transaction.created_at >= start
            )
        )
        referrals = await session.scalar(
            select(func.coalesce(func.sum(Transaction.amount), 0)).where(
                Transaction.type == TransactionType.REFERRAL, Transaction.created_at >= start
            )
        )
        refunds = await session.scalar(
            select(func.coalesce(func.sum(Transaction.amount), 0)).where(
                Transaction.type == TransactionType.REFUND, Transaction.created_at >= start
            )
        )
        new_users = await session.scalar(
            select(func.count(User.id)).where(User.created_at >= start)
        )
        new_orders = await session.scalar(
            select(func.count(Order.id)).where(Order.created_at >= start)
        )

    text = (
        f"📊 <b>Отчет за {label}</b> ({start.strftime('%d.%m.%Y')} — {now.strftime('%d.%m.%Y')})\n\n"
        f"📥 Пополнения: {deposits:.2f} ₽\n"
        f"📤 Покупки: {abs(purchases):.2f} ₽\n"
        f"🎁 Реф. бонусы: {referrals:.2f} ₽\n"
        f"💸 Возвраты: {refunds:.2f} ₽\n"
        f"📈 <b>Чистая прибыль: {(deposits + purchases + referrals + refunds):.2f} ₽</b>\n\n"
        f"👥 Новых пользователей: {new_users}\n"
        f"📋 Новых заказов: {new_orders}"
    )

    kb = InlineKeyboardMarkup().add(InlineKeyboardButton("🔙 Назад", callback_data="admin_finance"))

    if message_id:
        await bot.edit_message_text(text, chat_id, message_id, parse_mode="HTML", reply_markup=kb)
    else:
        await bot.send_message(chat_id, text, parse_mode="HTML", reply_markup=kb)


async def show_admin_settings(bot: TeleBot, chat_id: int, message_id: int = None):
    async with AsyncSessionLocal() as session:
        maintenance = await session.get(Setting, "maintenance_mode")
        maintenance_mode = maintenance.value == "true" if maintenance else False

    text = (
        f"⚙️ <b>Настройки</b>\n\n"
        f"💲 Мин. пополнение: {config.MIN_DEPOSIT} ₽\n"
        f"🎁 Реф. бонус: {config.REFERRAL_BONUS} ₽\n"
        f"📈 Наценка на прокси: {config.PROXY_MARKUP_PERCENT * 100:.0f}%\n"
        f"🔧 Тех. работы: {'Включены' if maintenance_mode else 'Выключены'}\n\n"
        f"Выберите параметр для изменения:"
    )

    if message_id:
        await bot.edit_message_text(text, chat_id, message_id, parse_mode="HTML", reply_markup=get_admin_settings_keyboard())
    else:
        await bot.send_message(chat_id, text, parse_mode="HTML", reply_markup=get_admin_settings_keyboard())


async def sync_proxies_from_api(bot: TeleBot, chat_id: int):
    """Sync proxies from Proxy6.net API"""
    async with AsyncSessionLocal() as session:
        # Get all proxies from API
        api_proxies = await proxy6_client.get_proxies("active")
        synced = 0
        for ap in api_proxies:
            # Check if exists
            existing = await session.scalar(
                select(Proxy).where(Proxy.proxy6_id == ap.id)
            )
            if existing:
                # Update
                existing.ip = ap.ip
                existing.port = ap.port
                existing.login = ap.user
                existing.password = ap.password
                existing.type = ProxyType(ap.type)
                existing.country = ap.country
                existing.city = ap.city
                existing.isp = ap.isp
                existing.expires_at = datetime.fromisoformat(ap.date_end.replace('Z', '+00:00')) if ap.date_end else None
                existing.price_per_month = ap.price
                existing.sale_price = ap.price * (1 + config.PROXY_MARKUP_PERCENT)
                existing.status = ProxyStatus.AVAILABLE if not existing.user_id else ProxyStatus.SOLD
            else:
                # Create new
                proxy = Proxy(
                    proxy6_id=ap.id,
                    ip=ap.ip,
                    port=ap.port,
                    login=ap.user,
                    password=ap.password,
                    type=ProxyType(ap.type),
                    country=ap.country,
                    city=ap.city,
                    isp=ap.isp,
                    status=ProxyStatus.AVAILABLE,
                    price_per_month=ap.price,
                    sale_price=ap.price * (1 + config.PROXY_MARKUP_PERCENT),
                    expires_at=datetime.fromisoformat(ap.date_end.replace('Z', '+00:00')) if ap.date_end else None,
                )
                session.add(proxy)
            synced += 1
        await session.commit()

    await bot.send_message(chat_id, f"✅ Синхронизация завершена. Обновлено прокси: {synced}")


async def send_broadcast(bot: TeleBot, text: str) -> tuple[int, int]:
    """Send broadcast to all users"""
    async with AsyncSessionLocal() as session:
        users = await session.scalars(
            select(User.id).where(User.is_banned == False)
        )
        user_ids = list(users)

    sent = 0
    failed = 0
    for uid in user_ids:
        try:
            await bot.send_message(uid, text, parse_mode="HTML")
            sent += 1
            await asyncio.sleep(0.05)  # Rate limit
        except Exception:
            failed += 1
    return sent, failed


# Import asyncio for broadcast
import asyncio


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
        f"💰 Цена закупки: {proxy.price_per_month:.2f} ₽/мес\n"
        f"💰 Цена продажи: {proxy.sale_price:.2f} ₽/мес\n"
        f"📅 До: {proxy.expires_at.strftime('%d.%m.%Y %H:%M') if proxy.expires_at else 'Не указано'}\n"
        f"Статус: {proxy.status.value}"
    )


# --- Text handlers for admin states ---

def register_admin_text_handlers(bot: TeleBot):

    @bot.message_handler(func=lambda m: is_admin(m.from_user.id) and admin_states.get(m.from_user.id) == AdminState.BROADCAST_TEXT)
    async def handle_broadcast_text(message: Message):
        admin_states[message.from_user.id] = AdminState.BROADCAST_CONFIRM
        admin_states[f"{message.from_user.id}_broadcast_text"] = message.text
        await bot.send_message(
            message.chat.id,
            f"📢 <b>Подтверждение рассылки</b>\n\n"
            f"Текст сообщения:\n{message.text}\n\n"
            f"Отправить всем пользователям?",
            parse_mode="HTML",
            reply_markup=get_broadcast_confirm_keyboard()
        )

    @bot.message_handler(func=lambda m: is_admin(m.from_user.id) and admin_states.get(m.from_user.id) == AdminState.SEARCH_USER)
    async def handle_search_user(message: Message):
        admin_states.pop(message.from_user.id, None)
        query = message.text.strip()
        async with AsyncSessionLocal() as session:
            if query.isdigit():
                user = await session.get(User, int(query))
                users = [user] if user else []
            else:
                users = await session.scalars(
                    select(User).where(
                        or_(
                            User.username.ilike(f"%{query}%"),
                            User.first_name.ilike(f"%{query}%"),
                        )
                    ).limit(10)
                )
                users = list(users)

        if not users:
            await bot.send_message(message.chat.id, "Пользователи не найдены", reply_markup=get_admin_main_keyboard())
            return

        for u in users:
            await show_user_details(bot, message.chat.id, u.id)

    @bot.message_handler(func=lambda m: is_admin(m.from_user.id) and admin_states.get(m.from_user.id) == AdminState.CHANGE_BALANCE)
    async def handle_change_balance(message: Message):
        admin_states.pop(message.from_user.id, None)
        target_id = admin_states.pop(f"{message.from_user.id}_target_user", None)
        if not target_id:
            await bot.send_message(message.chat.id, "Ошибка: пользователь не найден")
            return

        try:
            amount = float(message.text.strip())
        except ValueError:
            await bot.send_message(message.chat.id, "❌ Введите число")
            return

        async with AsyncSessionLocal() as session:
            user = await session.get(User, target_id)
            if not user:
                await bot.send_message(message.chat.id, "Пользователь не найден")
                return

            old_balance = user.balance
            user.balance += amount
            session.add(Transaction(
                user_id=user.id,
                type=TransactionType.DEPOSIT if amount > 0 else TransactionType.WITHDRAWAL,
                amount=amount,
                balance_before=old_balance,
                balance_after=user.balance,
                description=f"Админское изменение баланса ({'+' if amount > 0 else ''}{amount:.2f} ₽)",
            ))
            await session.commit()

        await bot.send_message(
            message.chat.id,
            f"✅ Баланс пользователя {target_id} изменен на {amount:+.2f} ₽\n"
            f"Было: {old_balance:.2f} ₽ → Стало: {user.balance:.2f} ₽",
            reply_markup=get_admin_main_keyboard()
        )

    @bot.message_handler(func=lambda m: is_admin(m.from_user.id) and admin_states.get(m.from_user.id) == AdminState.MESSAGE_USER)
    async def handle_message_user(message: Message):
        admin_states.pop(message.from_user.id, None)
        target_id = admin_states.pop(f"{message.from_user.id}_target_user", None)
        if not target_id:
            await bot.send_message(message.chat.id, "Ошибка: пользователь не найден")
            return

        try:
            await bot.send_message(target_id, f"💬 <b>Сообщение от администрации:</b>\n\n{message.text}", parse_mode="HTML")
            await bot.send_message(message.chat.id, "✅ Сообщение доставлено", reply_markup=get_admin_main_keyboard())
        except Exception as e:
            await bot.send_message(message.chat.id, f"❌ Ошибка отправки: {e}", reply_markup=get_admin_main_keyboard())

    @bot.message_handler(func=lambda m: is_admin(m.from_user.id) and admin_states.get(m.from_user.id) == AdminState.SET_MIN_DEPOSIT)
    async def handle_set_min_deposit(message: Message):
        admin_states.pop(message.from_user.id, None)
        try:
            value = int(message.text.strip())
            if value < 1:
                raise ValueError
        except ValueError:
            await bot.send_message(message.chat.id, "❌ Введите положительное число")
            return

        # Update config (in memory, for persistence need to save to DB)
        config.MIN_DEPOSIT = value
        await bot.send_message(message.chat.id, f"✅ Минимальное пополнение установлено: {value} ₽", reply_markup=get_admin_main_keyboard())

    @bot.message_handler(func=lambda m: is_admin(m.from_user.id) and admin_states.get(m.from_user.id) == AdminState.SET_REF_BONUS)
    async def handle_set_ref_bonus(message: Message):
        admin_states.pop(message.from_user.id, None)
        try:
            value = int(message.text.strip())
            if value < 0:
                raise ValueError
        except ValueError:
            await bot.send_message(message.chat.id, "❌ Введите число >= 0")
            return

        config.REFERRAL_BONUS = value
        await bot.send_message(message.chat.id, f"✅ Реферальный бонус установлен: {value} ₽", reply_markup=get_admin_main_keyboard())

    @bot.message_handler(func=lambda m: is_admin(m.from_user.id) and admin_states.get(m.from_user.id) == AdminState.SET_MARKUP)
    async def handle_set_markup(message: Message):
        admin_states.pop(message.from_user.id, None)
        try:
            value = float(message.text.strip())
            if value < 0 or value > 10:
                raise ValueError
        except ValueError:
            await bot.send_message(message.chat.id, "❌ Введите процент (0-1000)")
            return

        config.PROXY_MARKUP_PERCENT = value / 100
        await bot.send_message(message.chat.id, f"✅ Наценка установлена: {value}%", reply_markup=get_admin_main_keyboard())

    @bot.message_handler(func=lambda m: is_admin(m.from_user.id) and admin_states.get(m.from_user.id) == AdminState.ADD_PROXY)
    async def handle_add_proxy(message: Message):
        admin_states.pop(message.from_user.id, None)
        parts = message.text.strip().split("|")
        if len(parts) < 11:
            await bot.send_message(message.chat.id, "❌ Неверный формат. Нужно 11 полей через |")
            return

        try:
            p_type, ip, port, login, password, country, city, isp, buy_price, sell_price, days = parts
            port = int(port)
            buy_price = float(buy_price)
            sell_price = float(sell_price)
            days = int(days)
        except ValueError:
            await bot.send_message(message.chat.id, "❌ Ошибка в числовых полях")
            return

        if p_type not in [t.value for t in ProxyType]:
            await bot.send_message(message.chat.id, f"❌ Неверный тип. Допустимы: {[t.value for t in ProxyType]}")
            return

        async with AsyncSessionLocal() as session:
            proxy = Proxy(
                ip=ip,
                port=port,
                login=login if login else None,
                password=password if password else None,
                type=ProxyType(p_type),
                country=country if country else None,
                city=city if city else None,
                isp=isp if isp else None,
                status=ProxyStatus.AVAILABLE,
                price_per_month=buy_price,
                sale_price=sell_price,
                expires_at=datetime.utcnow() + timedelta(days=days),
            )
            session.add(proxy)
            await session.commit()

        await bot.send_message(message.chat.id, f"✅ Прокси добавлен: {ip}:{port}", reply_markup=get_admin_main_keyboard())