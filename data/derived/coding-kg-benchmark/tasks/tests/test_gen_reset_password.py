"""Test: gen-reset-password — reset_password function."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "example-repo", "src"))
import pytest
import user_service

@pytest.fixture(autouse=True)
def clear_dbs():
    user_service._user_db.clear()
    yield
    user_service._user_db.clear()

def test_reset_password_success():
    user_service.register_user("test@example.com", "Test", "oldpass")
    result = user_service.reset_password("user_1", "oldpass", "newpass")
    assert result is True
    # Verify new password works
    authed = user_service.authenticate_user("test@example.com", "newpass")
    assert authed is not None

def test_reset_wrong_old_password():
    user_service.register_user("test@example.com", "Test", "oldpass")
    result = user_service.reset_password("user_1", "wrongpass", "newpass")
    assert result is False

def test_reset_nonexistent_user():
    result = user_service.reset_password("nonexistent", "old", "new")
    assert result is False

def test_reset_uses_new_password_for_auth():
    user_service.register_user("test@example.com", "Test", "oldpass")
    user_service.reset_password("user_1", "oldpass", "newpass")
    # Old password should fail
    assert user_service.authenticate_user("test@example.com", "oldpass") is None
    # New password should work
    assert user_service.authenticate_user("test@example.com", "newpass") is not None