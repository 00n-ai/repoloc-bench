"""Tests for user_service module."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest
from user_service import (
    User, AdminUser, register_user, authenticate_user,
    get_user_profile, update_user_profile, list_users_by_role,
    delete_user, promote_to_admin, hash_password, verify_password
)


class TestUser:
    def test_user_creation(self):
        user = User("user_1", "test@example.com", "Test User")
        assert user.user_id == "user_1"
        assert user.email == "test@example.com"
        assert user.role == "member"

    def test_email_validation_lowercase(self):
        user = User("user_1", "Test@EXAMPLE.com", "Test")
        assert user.email == "test@example.com"

    def test_invalid_email_raises(self):
        with pytest.raises(ValueError, match="Invalid email"):
            User("user_1", "not-an-email", "Test")

    def test_to_dict(self):
        user = User("user_1", "test@example.com", "Test")
        d = user.to_dict()
        assert d["user_id"] == "user_1"
        assert d["email"] == "test@example.com"
        assert d["role"] == "member"
        assert d["last_login"] is None


class TestAdminUser:
    def test_admin_has_admin_role(self):
        admin = AdminUser("admin_1", "admin@example.com", "Admin")
        assert admin.role == "admin"

    def test_admin_permissions(self):
        admin = AdminUser("admin_1", "admin@example.com", "Admin")
        assert admin.has_permission("read")
        assert admin.has_permission("write")
        assert admin.has_permission("delete")
        assert not admin.has_permission("superadmin")

    def test_admin_to_dict_includes_permissions(self):
        admin = AdminUser("admin_1", "admin@example.com", "Admin")
        d = admin.to_dict()
        assert "permissions" in d
        assert "read" in d["permissions"]


class TestPasswordHashing:
    def test_hash_password_format(self):
        h = hash_password("mypassword")
        assert "$" in h
        salt, hash_val = h.split("$")
        assert len(salt) == 32  # 16 bytes hex
        assert len(hash_val) == 64  # sha256 hex

    def test_verify_correct_password(self):
        h = hash_password("mypassword")
        assert verify_password("mypassword", h) is True

    def test_verify_wrong_password(self):
        h = hash_password("mypassword")
        assert verify_password("wrongpassword", h) is False

    def test_verify_malformed_hash(self):
        assert verify_password("password", "malformed") is False


class TestUserService:
    def setup_method(self):
        """Clear user db before each test."""
        import user_service
        user_service._user_db.clear()

    def test_register_user(self):
        user = register_user("new@example.com", "New User", "password123")
        assert user.user_id == "user_1"
        assert user.email == "new@example.com"
        assert user.password_hash is not None

    def test_register_duplicate_email_raises(self):
        register_user("dup@example.com", "First", "pass")
        with pytest.raises(ValueError, match="already exists"):
            register_user("dup@example.com", "Second", "pass")

    def test_authenticate_valid(self):
        register_user("auth@example.com", "Auth User", "secret")
        user = authenticate_user("auth@example.com", "secret")
        assert user is not None
        assert user.email == "auth@example.com"
        assert user.last_login is not None

    def test_authenticate_wrong_password(self):
        register_user("auth@example.com", "Auth User", "secret")
        user = authenticate_user("auth@example.com", "wrong")
        assert user is None

    def test_authenticate_nonexistent_user(self):
        user = authenticate_user("nobody@example.com", "pass")
        assert user is None

    def test_get_user_profile(self):
        reg = register_user("profile@example.com", "Profile", "pass")
        profile = get_user_profile(reg.user_id)
        assert profile is not None
        assert profile["email"] == "profile@example.com"

    def test_get_user_profile_not_found(self):
        assert get_user_profile("nonexistent") is None

    def test_update_user_profile_name(self):
        reg = register_user("update@example.com", "Original", "pass")
        updated = update_user_profile("user_1", name="Updated Name")
        assert updated.name == "Updated Name"

    def test_update_user_profile_email(self):
        reg = register_user("update@example.com", "Original", "pass")
        updated = update_user_profile("user_1", email="new@example.com")
        assert updated.email == "new@example.com"

    def test_update_nonexistent_user(self):
        assert update_user_profile("nonexistent", name="X") is None

    def test_list_users_by_role(self):
        register_user("a@example.com", "A", "pass")
        register_user("b@example.com", "B", "pass")
        members = list_users_by_role("member")
        assert len(members) == 2

    def test_delete_user(self):
        reg = register_user("delete@example.com", "Delete", "pass")
        assert delete_user(reg.user_id) is True
        assert get_user_profile(reg.user_id) is None

    def test_delete_nonexistent_user(self):
        assert delete_user("nonexistent") is False

    def test_promote_to_admin(self):
        reg = register_user("promote@example.com", "Promote", "pass")
        admin = promote_to_admin(reg.user_id)
        assert admin is not None
        assert admin.role == "admin"
        assert admin.has_permission("delete")

    def test_promote_nonexistent(self):
        assert promote_to_admin("nonexistent") is None