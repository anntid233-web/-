import uuid
import hmac
import hashlib
import json
from dataclasses import dataclass
from typing import Optional
from yookassa import Configuration, Payment, WebhookNotification
from yookassa.domain.notification import WebhookNotificationEventType
from config import config


@dataclass
class PaymentResult:
    payment_id: str
    confirmation_url: str
    status: str
    amount: float
    metadata: dict


class YooKassaClient:
    def __init__(self):
        Configuration.account_id = config.YOOKASSA_SHOP_ID
        Configuration.secret_key = config.YOOKASSA_SECRET_KEY

    def create_payment(
        self,
        amount: float,
        description: str,
        metadata: dict,
        return_url: Optional[str] = None,
        capture: bool = True,
    ) -> PaymentResult:
        """Create a payment in YooKassa"""
        payment = Payment.create({
            "amount": {
                "value": f"{amount:.2f}",
                "currency": "RUB"
            },
            "confirmation": {
                "type": "redirect",
                "return_url": return_url or config.YOOKASSA_RETURN_URL
            },
            "capture": capture,
            "description": description,
            "metadata": metadata,
        }, uuid.uuid4())

        return PaymentResult(
            payment_id=payment.id,
            confirmation_url=payment.confirmation.confirmation_url,
            status=payment.status,
            amount=amount,
            metadata=metadata,
        )

    def get_payment(self, payment_id: str) -> PaymentResult:
        """Get payment info by ID"""
        payment = Payment.find_one(payment_id)
        return PaymentResult(
            payment_id=payment.id,
            confirmation_url=payment.confirmation.confirmation_url if payment.confirmation else "",
            status=payment.status,
            amount=float(payment.amount.value),
            metadata=payment.metadata or {},
        )

    def capture_payment(self, payment_id: str, amount: Optional[float] = None) -> PaymentResult:
        """Capture a previously authorized payment"""
        capture_data = {}
        if amount:
            capture_data["amount"] = {
                "value": f"{amount:.2f}",
                "currency": "RUB"
            }
        payment = Payment.capture(payment_id, capture_data, uuid.uuid4())
        return PaymentResult(
            payment_id=payment.id,
            confirmation_url=payment.confirmation.confirmation_url if payment.confirmation else "",
            status=payment.status,
            amount=float(payment.amount.value),
            metadata=payment.metadata or {},
        )

    def cancel_payment(self, payment_id: str) -> PaymentResult:
        """Cancel a payment"""
        payment = Payment.cancel(payment_id, uuid.uuid4())
        return PaymentResult(
            payment_id=payment.id,
            confirmation_url=payment.confirmation.confirmation_url if payment.confirmation else "",
            status=payment.status,
            amount=float(payment.amount.value),
            metadata=payment.metadata or {},
        )

    def verify_webhook_signature(self, body: bytes, signature: str) -> bool:
        """Verify webhook signature from YooKassa"""
        if not config.YOOKASSA_WEBHOOK_SECRET:
            return True  # Skip verification if secret not set

        expected_signature = hmac.new(
            config.YOOKASSA_WEBHOOK_SECRET.encode(),
            body,
            hashlib.sha256
        ).hexdigest()

        return hmac.compare_digest(expected_signature, signature)

    def parse_webhook(self, body: bytes, signature: str) -> Optional[WebhookNotification]:
        """Parse and verify webhook notification"""
        if not self.verify_webhook_signature(body, signature):
            return None

        try:
            notification = WebhookNotification(json.loads(body.decode()))
            return notification
        except Exception:
            return None

    @staticmethod
    def is_payment_successful(notification: WebhookNotification) -> bool:
        """Check if webhook indicates successful payment"""
        return (
            notification.event == WebhookNotificationEventType.PAYMENT_SUCCEEDED
            and notification.object.status == "succeeded"
        )

    @staticmethod
    def is_payment_failed(notification: WebhookNotification) -> bool:
        """Check if webhook indicates failed payment"""
        return (
            notification.event == WebhookNotificationEventType.PAYMENT_CANCELED
            or (notification.event == WebhookNotificationEventType.PAYMENT_SUCCEEDED
                and notification.object.status == "canceled")
        )


yookassa_client = YooKassaClient()