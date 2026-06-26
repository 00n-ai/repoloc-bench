"""Tests for notifications module."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest
from notifications import (
    NotificationType, queue_notification, send_email,
    notify_welcome, notify_payment_confirmation, notify_payment_failed,
    notify_password_reset, flush_notification_queue, get_user_notifications
)
import notifications


class TestNotifications:
    def setup_method(self):
        notifications._notification_queue.clear()

    def test_queue_notification(self):
        notif = queue_notification("user_1", NotificationType.WELCOME, "Welcome!")
        assert notif["id"] == "notif_1"
        assert notif["user_id"] == "user_1"
        assert notif["type"] == "welcome"
        assert notif["message"] == "Welcome!"
        assert notif["sent_at"] is None

    def test_send_email(self):
        result = send_email("test@example.com", "Subject", "Body")
        assert result is True

    def test_notify_welcome(self):
        result = notify_welcome("user@example.com", "John")
        assert result is True

    def test_notify_payment_confirmation(self):
        result = notify_payment_confirmation("user@example.com", 49.99, "pro")
        assert result is True

    def test_notify_payment_failed(self):
        result = notify_payment_failed("user@example.com", 49.99)
        assert result is True

    def test_notify_password_reset(self):
        result = notify_password_reset("user@example.com", "reset_token_123")
        assert result is True

    def test_flush_notification_queue(self):
        queue_notification("user_1", NotificationType.WELCOME, "Welcome")
        queue_notification("user_2", NotificationType.PAYMENT_CONFIRMATION, "Payment done")
        sent = flush_notification_queue()
        assert len(sent) == 2
        assert all(s["sent_at"] is not None for s in sent)

    def test_flush_empty_queue(self):
        sent = flush_notification_queue()
        assert sent == []

    def test_get_user_notifications(self):
        queue_notification("user_1", NotificationType.WELCOME, "Welcome")
        queue_notification("user_2", NotificationType.WELCOME, "Welcome")
        queue_notification("user_1", NotificationType.PAYMENT_CONFIRMATION, "Payment")
        user_1_notifs = get_user_notifications("user_1")
        assert len(user_1_notifs) == 2
        assert all(n["user_id"] == "user_1" for n in user_1_notifs)

    def test_get_user_notifications_empty(self):
        assert get_user_notifications("nonexistent") == []