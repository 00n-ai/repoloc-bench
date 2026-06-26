"""Payments module — handles subscription payments, refunds, and billing logic."""

from typing import Optional, Dict, List
from datetime import datetime
from enum import Enum

# ─── Payment Models ───

class PaymentStatus(Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    REFUNDED = "refunded"


class SubscriptionTier(Enum):
    FREE = "free"
    PRO = "pro"
    ENTERPRISE = "enterprise"


class Payment:
    """Represents a single payment transaction."""
    def __init__(self, payment_id: str, user_id: str, amount: float, tier: SubscriptionTier):
        self.payment_id = payment_id
        self.user_id = user_id
        self.amount = self._validate_amount(amount)
        self.tier = tier
        self.status = PaymentStatus.PENDING
        self.created_at = datetime.utcnow()
        self.refunded_at: Optional[datetime] = None

    @staticmethod
    def _validate_amount(amount: float) -> float:
        """Validate payment amount is positive."""
        if amount < 0:
            raise ValueError("Payment amount cannot be negative")
        if amount > 100000:
            raise ValueError("Payment amount exceeds maximum ($100,000)")
        return round(amount, 2)

    def complete(self) -> None:
        """Mark payment as completed."""
        if self.status != PaymentStatus.PENDING:
            raise RuntimeError(f"Cannot complete payment in status {self.status}")
        self.status = PaymentStatus.COMPLETED

    def fail(self) -> None:
        """Mark payment as failed."""
        self.status = PaymentStatus.FAILED

    def refund(self) -> None:
        """Refund a completed payment."""
        if self.status != PaymentStatus.COMPLETED:
            raise RuntimeError("Can only refund completed payments")
        self.status = PaymentStatus.REFUNDED
        self.refunded_at = datetime.utcnow()

    def to_dict(self) -> dict:
        """Serialize payment to dictionary."""
        return {
            "payment_id": self.payment_id,
            "user_id": self.user_id,
            "amount": self.amount,
            "tier": self.tier.value,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "refunded_at": self.refunded_at.isoformat() if self.refunded_at else None,
        }


# ─── Billing Service ───

# In-memory storage
_payment_db: Dict[str, Payment] = {}
_payment_counter = 0

# We import user_service at runtime to avoid circular dependency
def _get_user_service():
    import user_service
    return user_service


def process_payment(user_id: str, amount: float, tier: SubscriptionTier) -> Payment:
    """Process a payment for a user subscription.
    Validates user exists before processing.
    """
    user_svc = _get_user_service()
    user = user_svc.get_user_profile(user_id)
    if not user:
        raise ValueError(f"User {user_id} not found")

    global _payment_counter
    payment_id = f"pay_{_payment_counter + 1}"
    _payment_counter += 1

    payment = Payment(payment_id, user_id, amount, tier)
    _payment_db[payment_id] = payment

    # Simulate payment processing
    try:
        # In real system: charge via Stripe/PayPal
        payment.complete()
    except Exception:
        payment.fail()

    return payment


def refund_payment(payment_id: str) -> Optional[Payment]:
    """Refund a payment by ID. Returns updated Payment or None if not found."""
    payment = _payment_db.get(payment_id)
    if not payment:
        return None
    payment.refund()
    return payment


def get_payment_history(user_id: str) -> List[Payment]:
    """Get all payments for a user."""
    return [p for p in _payment_db.values() if p.user_id == user_id]


def get_revenue_by_tier(tier: SubscriptionTier) -> float:
    """Calculate total revenue for a subscription tier (completed payments only)."""
    total = sum(
        p.amount for p in _payment_db.values()
        if p.tier == tier and p.status == PaymentStatus.COMPLETED
    )
    return round(total, 2)


def get_user_subscription_tier(user_id: str) -> Optional[SubscriptionTier]:
    """Get a user's current subscription tier (highest active tier)."""
    user_payments = get_payment_history(user_id)
    active_tiers = [
        p.tier for p in user_payments
        if p.status == PaymentStatus.COMPLETED
    ]
    if not active_tiers:
        return None
    # Priority: enterprise > pro > free
    priority = {SubscriptionTier.ENTERPRISE: 3, SubscriptionTier.PRO: 2, SubscriptionTier.FREE: 1}
    return max(active_tiers, key=lambda t: priority[t])