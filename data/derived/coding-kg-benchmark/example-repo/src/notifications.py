"""Notifications module — sends email and push notifications for user events."""

from typing import Optional, Dict, List
from datetime import datetime
import smtplib
from email.mime.text import MIMEText


# ─── Notification Types ───

class NotificationType:
    WELCOME = "welcome"
    PAYMENT_CONFIRMATION = "payment_confirmation"
    PAYMENT_FAILED = "payment_failed"
    PASSWORD_RESET = "password_reset"
    ACCOUNT_DELETED = "account_deleted"


# ─── Notification Queue (in-memory) ───

_notification_queue: List[dict] = []


def queue_notification(user_id: str, notification_type: str, message: str) -> dict:
    """Queue a notification for later sending."""
    notification = {
        "id": f"notif_{len(_notification_queue) + 1}",
        "user_id": user_id,
        "type": notification_type,
        "message": message,
        "created_at": datetime.utcnow().isoformat(),
        "sent_at": None,
    }
    _notification_queue.append(notification)
    return notification


def send_email(to_address: str, subject: str, body: str) -> bool:
    """Send an email. Returns True if successful, False otherwise.
    In production this would use a real SMTP server.
    """
    try:
        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = "noreply@example.com"
        msg["To"] = to_address
        # In production: connect to SMTP and send
        # with smtplib.SMTP(smtp_host, smtp_port) as server:
        #     server.sendmail(...)
        print(f"[EMAIL] To: {to_address} | Subject: {subject}")
    except Exception as e:
        print(f"[EMAIL ERROR] {e}")
        return False
    return True


def notify_welcome(user_email: str, user_name: str) -> bool:
    """Send a welcome email to a new user."""
    subject = "Welcome to Our Platform!"
    body = f"Hi {user_name},\n\nWelcome to our platform! Your account has been created successfully."
    return send_email(user_email, subject, body)


def notify_payment_confirmation(user_email: str, amount: float, tier: str) -> bool:
    """Send a payment confirmation email."""
    subject = f"Payment Confirmation - {tier.capitalize()} Plan"
    body = f"Your payment of ${amount:.2f} for the {tier} plan has been processed successfully."
    return send_email(user_email, subject, body)


def notify_payment_failed(user_email: str, amount: float) -> bool:
    """Send a payment failure notification."""
    subject = "Payment Failed"
    body = f"Your payment of ${amount:.2f} could not be processed. Please update your payment method."
    return send_email(user_email, subject, body)


def notify_password_reset(user_email: str, reset_token: str) -> bool:
    """Send a password reset email with a reset link."""
    subject = "Password Reset Request"
    body = f"Click the following link to reset your password:\nhttps://example.com/reset?token={reset_token}"
    return send_email(user_email, subject, body)


def flush_notification_queue() -> List[dict]:
    """Send all queued notifications. Returns list of sent notifications."""
    sent = []
    for notif in _notification_queue:
        if notif["sent_at"] is None:
            # In production: look up user email from user_service
            notif["sent_at"] = datetime.utcnow().isoformat()
            sent.append(notif)
    _notification_queue.clear()
    return sent


def get_user_notifications(user_id: str) -> List[dict]:
    """Get all notifications for a specific user."""
    return [n for n in _notification_queue if n["user_id"] == user_id]