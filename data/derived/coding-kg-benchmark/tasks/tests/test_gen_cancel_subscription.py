"""Test: gen-cancel-subscription — cancel_subscription function."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "example-repo", "src"))
import pytest
import payments
import user_service
from payments import PaymentStatus, SubscriptionTier, Payment

@pytest.fixture(autouse=True)
def clear_dbs():
    payments._payment_db.clear()
    payments._payment_counter = 0
    user_service._user_db.clear()
    yield
    payments._payment_db.clear()
    payments._payment_counter = 0
    user_service._user_db.clear()

# Import the generated function (will be added by experiment runner)
# from payments import cancel_subscription

def test_cancels_active_subscription():
    user_service.register_user("test@example.com", "Test", "pass")
    payments.process_payment("user_1", 49.99, SubscriptionTier.PRO)
    result = payments.cancel_subscription("user_1")
    assert result is not None
    assert result.status == PaymentStatus.REFUNDED

def test_returns_none_when_no_active():
    user_service.register_user("test@example.com", "Test", "pass")
    result = payments.cancel_subscription("user_1")
    assert result is None

def test_refunds_most_recent_when_multiple():
    user_service.register_user("test@example.com", "Test", "pass")
    p1 = payments.process_payment("user_1", 49.99, SubscriptionTier.PRO)
    p2 = payments.process_payment("user_1", 99, SubscriptionTier.ENTERPRISE)
    result = payments.cancel_subscription("user_1")
    assert result is not None
    assert result.payment_id == p2.payment_id

def test_nonexistent_user_raises():
    with pytest.raises(ValueError, match="not found"):
        payments.cancel_subscription("nonexistent")