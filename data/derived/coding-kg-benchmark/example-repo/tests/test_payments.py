"""Tests for payments module."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest
from payments import (
    Payment, PaymentStatus, SubscriptionTier,
    process_payment, refund_payment, get_payment_history,
    get_revenue_by_tier, get_user_subscription_tier
)
import user_service


class TestPayment:
    def test_payment_creation(self):
        p = Payment("pay_1", "user_1", 99.99, SubscriptionTier.PRO)
        assert p.payment_id == "pay_1"
        assert p.amount == 99.99
        assert p.tier == SubscriptionTier.PRO
        assert p.status == PaymentStatus.PENDING

    def test_negative_amount_raises(self):
        with pytest.raises(ValueError, match="cannot be negative"):
            Payment("pay_1", "user_1", -10, SubscriptionTier.PRO)

    def test_amount_over_max_raises(self):
        with pytest.raises(ValueError, match="exceeds maximum"):
            Payment("pay_1", "user_1", 200000, SubscriptionTier.ENTERPRISE)

    def test_complete_payment(self):
        p = Payment("pay_1", "user_1", 50, SubscriptionTier.PRO)
        p.complete()
        assert p.status == PaymentStatus.COMPLETED

    def test_complete_non_pending_raises(self):
        p = Payment("pay_1", "user_1", 50, SubscriptionTier.PRO)
        p.complete()
        with pytest.raises(RuntimeError, match="Cannot complete"):
            p.complete()

    def test_refund_completed(self):
        p = Payment("pay_1", "user_1", 50, SubscriptionTier.PRO)
        p.complete()
        p.refund()
        assert p.status == PaymentStatus.REFUNDED
        assert p.refunded_at is not None

    def test_refund_non_completed_raises(self):
        p = Payment("pay_1", "user_1", 50, SubscriptionTier.PRO)
        with pytest.raises(RuntimeError, match="only refund"):
            p.refund()

    def test_fail_payment(self):
        p = Payment("pay_1", "user_1", 50, SubscriptionTier.PRO)
        p.fail()
        assert p.status == PaymentStatus.FAILED

    def test_to_dict(self):
        p = Payment("pay_1", "user_1", 99.99, SubscriptionTier.PRO)
        d = p.to_dict()
        assert d["payment_id"] == "pay_1"
        assert d["amount"] == 99.99
        assert d["status"] == "pending"
        assert d["tier"] == "pro"


class TestBillingService:
    def setup_method(self):
        """Clear dbs before each test."""
        import payments
        payments._payment_db.clear()
        payments._payment_counter = 0
        user_service._user_db.clear()

    def test_process_payment_for_existing_user(self):
        user_service.register_user("pay@example.com", "Pay User", "pass")
        payment = process_payment("user_1", 49.99, SubscriptionTier.PRO)
        assert payment.payment_id == "pay_1"
        assert payment.status == PaymentStatus.COMPLETED

    def test_process_payment_nonexistent_user_raises(self):
        with pytest.raises(ValueError, match="not found"):
            process_payment("nonexistent", 49.99, SubscriptionTier.PRO)

    def test_refund_payment(self):
        user_service.register_user("pay@example.com", "Pay User", "pass")
        payment = process_payment("user_1", 99, SubscriptionTier.ENTERPRISE)
        refunded = refund_payment(payment.payment_id)
        assert refunded.status == PaymentStatus.REFUNDED

    def test_refund_nonexistent_payment(self):
        assert refund_payment("nonexistent") is None

    def test_get_payment_history(self):
        user_service.register_user("pay@example.com", "Pay User", "pass")
        process_payment("user_1", 49.99, SubscriptionTier.PRO)
        process_payment("user_1", 99, SubscriptionTier.ENTERPRISE)
        history = get_payment_history("user_1")
        assert len(history) == 2

    def test_get_revenue_by_tier(self):
        user_service.register_user("pay@example.com", "Pay User", "pass")
        process_payment("user_1", 49.99, SubscriptionTier.PRO)
        process_payment("user_1", 99, SubscriptionTier.PRO)
        revenue = get_revenue_by_tier(SubscriptionTier.PRO)
        assert revenue == 148.99

    def test_get_revenue_by_tier_excludes_refunded(self):
        user_service.register_user("pay@example.com", "Pay User", "pass")
        p1 = process_payment("user_1", 50, SubscriptionTier.PRO)
        process_payment("user_1", 100, SubscriptionTier.PRO)
        refund_payment(p1.payment_id)
        revenue = get_revenue_by_tier(SubscriptionTier.PRO)
        assert revenue == 100

    def test_get_user_subscription_tier(self):
        user_service.register_user("pay@example.com", "Pay User", "pass")
        process_payment("user_1", 49.99, SubscriptionTier.PRO)
        process_payment("user_1", 99, SubscriptionTier.ENTERPRISE)
        tier = get_user_subscription_tier("user_1")
        assert tier == SubscriptionTier.ENTERPRISE

    def test_get_user_subscription_tier_no_payments(self):
        user_service.register_user("pay@example.com", "Pay User", "pass")
        tier = get_user_subscription_tier("user_1")
        assert tier is None

    def test_get_user_subscription_tier_excludes_refunded(self):
        user_service.register_user("pay@example.com", "Pay User", "pass")
        p1 = process_payment("user_1", 99, SubscriptionTier.ENTERPRISE)
        process_payment("user_1", 49.99, SubscriptionTier.PRO)
        refund_payment(p1.payment_id)
        tier = get_user_subscription_tier("user_1")
        assert tier == SubscriptionTier.PRO