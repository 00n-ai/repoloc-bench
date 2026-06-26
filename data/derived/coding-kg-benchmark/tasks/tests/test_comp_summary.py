"""Test: comp-payment-summary — get_payment_summary function."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "example-repo", "src"))
import pytest
import payments
import user_service
from payments import PaymentStatus, SubscriptionTier

@pytest.fixture(autouse=True)
def clear_dbs():
    payments._payment_db.clear()
    payments._payment_counter = 0
    user_service._user_db.clear()
    yield
    payments._payment_db.clear()
    payments._payment_counter = 0
    user_service._user_db.clear()

def test_summary_returns_all_fields():
    user_service.register_user("test@example.com", "Test", "pass")
    payments.process_payment("user_1", 50, SubscriptionTier.PRO)
    summary = payments.get_payment_summary()
    assert "total_revenue" in summary
    assert "total_refunded" in summary
    assert "payment_count" in summary
    assert "active_subscribers" in summary

def test_summary_revenue_calculation():
    user_service.register_user("test@example.com", "Test", "pass")
    payments.process_payment("user_1", 50, SubscriptionTier.PRO)
    payments.process_payment("user_1", 100, SubscriptionTier.ENTERPRISE)
    summary = payments.get_payment_summary()
    assert summary["total_revenue"] == 150

def test_summary_refunded_calculation():
    user_service.register_user("test@example.com", "Test", "pass")
    p1 = payments.process_payment("user_1", 50, SubscriptionTier.PRO)
    payments.process_payment("user_1", 100, SubscriptionTier.ENTERPRISE)
    payments.refund_payment(p1.payment_id)
    summary = payments.get_payment_summary()
    assert summary["total_refunded"] == 50

def test_summary_active_subscribers():
    user_service.register_user("a@example.com", "A", "pass")
    user_service.register_user("b@example.com", "B", "pass")
    payments.process_payment("user_1", 50, SubscriptionTier.PRO)
    payments.process_payment("user_2", 100, SubscriptionTier.ENTERPRISE)
    summary = payments.get_payment_summary()
    assert summary["active_subscribers"] == 2

def test_summary_empty_when_no_payments():
    summary = payments.get_payment_summary()
    assert summary["total_revenue"] == 0
    assert summary["total_refunded"] == 0
    assert summary["payment_count"] == 0
    assert summary["active_subscribers"] == 0