import hmac
import hashlib
import json
import secrets
import aiohttp
from config import config
from database import create_transaction, complete_transaction, update_balance, get_user
from datetime import datetime


class PaymentProvider:
    """Base payment provider class."""
    
    async def create_payment(self, user_id: int, amount: float, description: str) -> dict:
        raise NotImplementedError
    
    async def check_payment(self, payment_id: str) -> bool:
        raise NotImplementedError
    
    def verify_webhook(self, data: dict, signature: str) -> bool:
        raise NotImplementedError


class CryptoBotProvider(PaymentProvider):
    """CryptoBot payment provider."""
    
    def __init__(self):
        self.token = config.CRYPTOBOT_TOKEN
        self.api_url = "https://pay.crypt.bot/api"
        self.headers = {"Crypto-Pay-API-Token": self.token}
    
    async def create_payment(self, user_id: int, amount: float, description: str) -> dict:
        """Create invoice in CryptoBot."""
        payload = {
            "asset": "USDT",
            "amount": str(amount),
            "description": description,
            "hidden_message": f"Пополнение баланса для пользователя {user_id}",
            "payload": f"deposit_{user_id}_{secrets.token_hex(8)}",
            "allow_comments": False,
            "allow_anonymous": False,
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(f"{self.api_url}/createInvoice", headers=self.headers, json=payload) as resp:
                result = await resp.json()
                
        if result.get("ok"):
            invoice = result["result"]
            payment_id = invoice["invoice_id"]
            await create_transaction(user_id, amount, "deposit", "cryptobot", str(payment_id), description)
            return {
                "payment_id": str(payment_id),
                "pay_url": invoice["bot_invoice_url"],
                "amount": amount,
                "currency": "USDT"
            }
        else:
            raise Exception(f"CryptoBot error: {result.get('error', 'Unknown error')}")
    
    async def check_payment(self, payment_id: str) -> bool:
        """Check invoice status."""
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{self.api_url}/getInvoices?invoice_ids={payment_id}", headers=self.headers) as resp:
                result = await resp.json()
        
        if result.get("ok") and result["result"]["items"]:
            invoice = result["result"]["items"][0]
            return invoice["status"] == "paid"
        return False
    
    def verify_webhook(self, data: dict, signature: str) -> bool:
        """Verify CryptoBot webhook signature."""
        if not self.token:
            return False
        check_string = json.dumps(data, separators=(",", ":"), ensure_ascii=False)
        expected = hmac.new(self.token.encode(), check_string.encode(), hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, signature)


class YooMoneyProvider(PaymentProvider):
    """YooMoney payment provider."""
    
    def __init__(self):
        self.token = config.YOOMONEY_TOKEN
        self.wallet = config.YOOMONEY_WALLET
        self.api_url = "https://yoomoney.ru/api"
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    async def create_payment(self, user_id: int, amount: float, description: str) -> dict:
        """Create quickpay link for YooMoney."""
        label = f"deposit_{user_id}_{secrets.token_hex(8)}"
        pay_url = (
            f"https://yoomoney.ru/quickpay/confirm.xml?"
            f"receiver={self.wallet}&"
            f"quickpay-form=shop&"
            f"targets={description}&"
            f"paymentType=SB&"
            f"sum={amount}&"
            f"label={label}"
        )
        
        await create_transaction(user_id, amount, "deposit", "yoomoney", label, description)
        
        return {
            "payment_id": label,
            "pay_url": pay_url,
            "amount": amount,
            "currency": "RUB"
        }
    
    async def check_payment(self, payment_id: str) -> bool:
        """Check payment history for label."""
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.api_url}/operation-history",
                headers=self.headers,
                data={"label": payment_id, "records": 1}
            ) as resp:
                result = await resp.json()
        
        if result.get("operations"):
            op = result["operations"][0]
            return op["status"] == "success" and op["direction"] == "in"
        return False
    
    def verify_webhook(self, data: dict, signature: str) -> bool:
        """YooMoney uses SHA1 for notifications."""
        # Implement if needed
        return True


def get_payment_provider(provider: str = None) -> PaymentProvider:
    """Get payment provider instance."""
    provider = provider or config.PAYMENT_PROVIDER
    if provider == "cryptobot":
        return CryptoBotProvider()
    elif provider == "yoomoney":
        return YooMoneyProvider()
    else:
        raise ValueError(f"Unknown payment provider: {provider}")


async def process_deposit(user_id: int, amount: float, provider: str = None) -> dict:
    """Process deposit for user."""
    provider_instance = get_payment_provider(provider)
    description = f"Пополнение баланса на {amount} {'USDT' if provider == 'cryptobot' else 'RUB'}"
    return await provider_instance.create_payment(user_id, amount, description)


async def handle_successful_payment(user_id: int, payment_id: str, provider: str):
    """Handle successful payment - update balance and mark transaction complete."""
    provider_instance = get_payment_provider(provider)
    
    # Verify payment
    if await provider_instance.check_payment(payment_id):
        async with aiosqlite.connect(config.DATABASE_PATH) as db:
            # Get transaction
            cursor = await db.execute(
                "SELECT * FROM transactions WHERE payment_id = ? AND user_id = ? AND status = 'pending'",
                (payment_id, user_id)
            )
            transaction = await cursor.fetchone()
            
            if transaction:
                # Update balance
                await db.execute(
                    "UPDATE users SET balance = balance + ?, updated_at = CURRENT_TIMESTAMP WHERE user_id = ?",
                    (transaction["amount"], user_id)
                )
                # Mark transaction complete
                await db.execute(
                    "UPDATE transactions SET status = 'completed', completed_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (transaction["id"],)
                )
                await db.commit()
                
                # Referral bonus
                await process_referral_bonus(user_id, transaction["amount"])
                
                return True, transaction["amount"]
    
    return False, 0


async def process_referral_bonus(user_id: int, amount: float):
    """Give referral bonus to referrer."""
    from database import get_user
    user = await get_user(user_id)
    if user and user["referred_by"]:
        bonus = amount * (config.REFERRAL_BONUS_PERCENT / 100)
        async with aiosqlite.connect(config.DATABASE_PATH) as db:
            await db.execute(
                "UPDATE users SET balance = balance + ?, updated_at = CURRENT_TIMESTAMP WHERE user_id = ?",
                (bonus, user["referred_by"])
            )
            await db.execute(
                """INSERT INTO transactions (user_id, amount, type, description)
                   VALUES (?, ?, 'referral_bonus', ?)""",
                (user["referred_by"], bonus, f"Реферальный бонус от пользователя {user_id}")
            )
            await db.commit()


# Import aiosqlite for the function above
import aiosqlite