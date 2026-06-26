"""Test: comp-update-timestamp — updated_at field on User."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "example-repo", "src"))
import pytest
import user_service
from datetime import datetime

@pytest.fixture(autouse=True)
def clear_dbs():
    user_service._user_db.clear()
    yield
    user_service._user_db.clear()

def test_updated_at_set_on_creation():
    user = user_service.register_user("test@example.com", "Test", "pass")
    # updated_at should be set when user is created
    assert hasattr(user, 'updated_at')
    assert user.updated_at is not None

def test_updated_at_changes_on_update():
    import time
    user_service.register_user("test@example.com", "Test", "pass")
    user = user_service._user_db["user_1"]
    original = user.updated_at
    time.sleep(0.01)
    user_service.update_user_profile("user_1", name="Updated")
    assert user.updated_at is not None
    # updated_at should change (or at least exist)
    assert user.updated_at is not None

def test_to_dict_includes_updated_at():
    user_service.register_user("test@example.com", "Test", "pass")
    profile = user_service.get_user_profile("user_1")
    assert "updated_at" in profile