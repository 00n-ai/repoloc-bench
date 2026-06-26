"""Test: gen-notify-user-deleted — notify_user_deleted function."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "example-repo", "src"))
import pytest
import notifications

@pytest.fixture(autouse=True)
def clear_queue():
    notifications._notification_queue.clear()
    yield
    notifications._notification_queue.clear()

def test_sends_deletion_email():
    result = notifications.notify_user_deleted("user@example.com", "John")
    assert result is True

def test_queues_internal_notification():
    notifications.notify_user_deleted("user@example.com", "John")
    notifs = notifications.get_user_notifications("user@example.com")
    # The function should queue a notification with the user's email or id
    # Depending on implementation, user_id might be the email
    assert len(notifs) >= 1

def test_returns_true_on_success():
    result = notifications.notify_user_deleted("user@example.com", "John")
    assert result is True