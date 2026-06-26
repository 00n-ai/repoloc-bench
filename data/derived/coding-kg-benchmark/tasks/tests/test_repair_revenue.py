"""Test: repair-revenue — fix get_revenue_by_tier to handle payment failures."""
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

def test_revenue_excludes_refunded():
    user_service.register_user("test@example.com", "Test", "pass")
    p1 = payments.process_payment("user_1", 50, SubscriptionTier.PRO)
    p2 = payments.process_payment("user_1", 100, SubscriptionTier.PRO)
    payments.refund_payment(p1.payment_id)
    revenue = payments.get_revenue_by_tier(SubscriptionTier.PRO)
    assert revenue == 100  # only p2, p1 was refunded

def test_revenue_includes_completed():
    user_service.register_user("test@example.com", "Test", "pass")
    payments.process_payment("user_1", 50, SubscriptionTier.PRO)
    payments.process_payment("user_1", 100, SubscriptionTier.PRO)
    revenue = payments.get_revenue_by_tier(SubscriptionTier.PRO)
    assert revenue == 150

def test_revenue_zero_when_all_refunded():
    user_service.register_user("test@example.com", "Test", "pass")
    p1 = payments.process_payment("user_1", 50, SubscriptionTier.PRO)
    payments.refund_payment(p1.payment_id)
    revenue = payments.get_revenue_by_tier(SubscriptionTier.PRO)
    assert revenue == 0