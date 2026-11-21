from aiohttp import web
import json
from payments.yookassa_client import yookassa_client
from database import (
    User, Order, Transaction, OrderStatus, TransactionType,
    AsyncSessionLocal
)
from handlers.user_handlers import fulfill_order
from config import config


async def yookassa_webhook(request: web.Request) -> web.Response:
    """Handle YooKassa webhook notifications"""
    # Verify signature
    signature = request.headers.get("X-YooKassa-Signature", "")
    body = await request.read()

    if not yookassa_client.verify_webhook_signature(body, signature):
        return web.Response(status=400, text="Invalid signature")

    try:
        notification = yookassa_client.parse_webhook(body, signature)
        if not notification:
            return web.Response(status=400, text="Invalid notification")

        # Handle payment events
        if yookassa_client.is_payment_successful(notification):
            await handle_successful_payment(notification.object)
        elif yookassa_client.is_payment_failed(notification):
            await handle_failed_payment(notification.object)

        return web.Response(status=200, text="OK")

    except Exception as e:
        print(f"Webhook error: {e}")
        return web.Response(status=500, text="Internal error")


async def handle_successful_payment(payment_obj):
    """Process successful payment"""
    metadata = payment_obj.metadata or {}
    payment_type = metadata.get("type")
    order_id = metadata.get("order_id")
    user_id = metadata.get("user_id")

    async with AsyncSessionLocal() as session:
        if payment_type == "proxy_purchase" and order_id:
            order = await session.get(Order, order_id)
            if order and order.status == OrderStatus.PENDING:
                order.status = OrderStatus.PAID
                await session.commit()
                # Fulfill order
                try:
                    # Import bot here to avoid circular import
                    from main import bot
                    await fulfill_order(bot, session, order)
                except Exception as e:
                    print(f"Error fulfilling order {order_id}: {e}")

        elif payment_type == "deposit" and user_id:
            user = await session.get(User, user_id)
            amount = metadata.get("amount", 0)
            if user:
                old_balance = user.balance
                user.balance += amount
                session.add(Transaction(
                    user_id=user.id,
                    type=TransactionType.DEPOSIT,
                    amount=amount,
                    balance_before=old_balance,
                    balance_after=user.balance,
                    description=f"Пополнение баланса через ЮKassa",
                    yookassa_payment_id=payment_obj.id,
                ))
                await session.commit()

                # Notify user
                try:
                    from main import bot
                    await bot.send_message(
                        user.id,
                        f"✅ <b>Баланс пополнен!</b>\n\n"
                        f"💰 Зачислено: {amount:.2f} ₽\n"
                        f"💳 Новый баланс: {user.balance:.2f} ₽",
                        parse_mode="HTML"
                    )
                except Exception:
                    pass


async def handle_failed_payment(payment_obj):
    """Process failed payment"""
    metadata = payment_obj.metadata or {}
    order_id = metadata.get("order_id")

    if order_id:
        async with AsyncSessionLocal() as session:
            order = await session.get(Order, order_id)
            if order and order.status == OrderStatus.PENDING:
                order.status = OrderStatus.FAILED
                await session.commit()

                try:
                    from main import bot
                    await bot.send_message(
                        order.user_id,
                        f"❌ <b>Оплата не прошла</b>\n\n"
                        f"Заказ #{order.id} отменен.\n"
                        f"Причина: {payment_obj.cancellation_details.reason if payment_obj.cancellation_details else 'Неизвестно'}",
                        parse_mode="HTML"
                    )
                except Exception:
                    pass


def setup_webhook(app: web.Application):
    """Setup webhook routes"""
    app.router.add_post(config.WEBHOOK_PATH, yookassa_webhook)
    # Health check
    app.router.add_get("/health", lambda r: web.Response(text="OK"))