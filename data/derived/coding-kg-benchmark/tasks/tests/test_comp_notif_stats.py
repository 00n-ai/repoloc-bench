"""Test: comp-notification-stats — get_notification_stats function."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "example-repo", "src"))
import pytest
import notifications
from notifications import NotificationType

@pytest.fixture(autouse=True)
def clear_queue():
    notifications._notification_queue.clear()
    yield
    notifications._notification_queue.clear()

def test_stats_returns_all_fields():
    notifications.queue_notification("user_1", NotificationType.WELCOME, "Welcome")
    stats = notifications.get_notification_stats()
    assert "total_queued" in stats
    assert "by_type" in stats
    assert "unsent_count" in stats

def test_stats_by_type_count():
    notifications.queue_notification("user_1", NotificationType.WELCOME, "Welcome")
    notifications.queue_notification("user_2", NotificationType.WELCOME, "Welcome")
    notifications.queue_notification("user_1", NotificationType.PAYMENT_CONFIRMATION, "Paid")
    stats = notifications.get_notification_stats()
    assert stats["by_type"]["welcome"] == 2
    assert stats["by_type"]["payment_confirmation"] == 1

def test_stats_unsent_count():
    notifications.queue_notification("user_1", NotificationType.WELCOME, "Welcome")
    notifications.queue_notification("user_2", NotificationType.PAYMENT_FAILED, "Failed")
    stats = notifications.get_notification_stats()
    assert stats["unsent_count"] == 2
    assert stats["total_queued"] == 2

def test_stats_empty_queue():
    stats = notifications.get_notification_stats()
    assert stats["total_queued"] == 0
    assert stats["unsent_count"] == 0
    assert stats["by_type"] == {}