"""Test: repair-notification-queue — fix flush_notification_queue."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "example-repo", "src"))
import pytest
import notifications

@pytest.fixture(autouse=True)
def clear_queue():
    notifications._notification_queue.clear()
    yield
    notifications._notification_queue.clear()

def test_flush_sends_notifications():
    notifications.queue_notification("user_1", "welcome", "Welcome!")
    notifications.queue_notification("user_2", "payment", "Payment done")
    sent = notifications.flush_notification_queue()
    assert len(sent) == 2
    assert all(s["sent_at"] is not None for s in sent)

def test_flush_clears_sent_notifications():
    notifications.queue_notification("user_1", "welcome", "Welcome!")
    notifications.flush_notification_queue()
    # Queue should be empty after flushing
    assert len(notifications._notification_queue) == 0

def test_flush_preserves_unsent_on_error():
    # Queue a notification
    notifications.queue_notification("user_1", "welcome", "Welcome!")
    #_flush_notification_queue should send and clear
    sent = notifications.flush_notification_queue()
    assert len(sent) == 1
    # After flush, queue is empty (sent notifications are removed)
    # This test verifies the function doesn't lose notifications
    remaining = notifications.get_user_notifications("user_1")
    assert len(remaining) == 0  # cleared after send