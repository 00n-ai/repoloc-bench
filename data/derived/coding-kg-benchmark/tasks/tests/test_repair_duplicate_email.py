"""Test: repair-duplicate-email — fix register_user duplicate check."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "example-repo", "src"))
import pytest
import user_service

@pytest.fixture(autouse=True)
def clear_dbs():
    user_service._user_db.clear()
    yield
    user_service._user_db.clear()

def test_duplicate_email_rejected():
    user_service.register_user("dup@example.com", "First", "pass")
    with pytest.raises(ValueError, match="already exists"):
        user_service.register_user("dup@example.com", "Second", "pass")

def test_duplicate_email_case_insensitive():
    user_service.register_user("Dup@Example.com", "First", "pass")
    with pytest.raises(ValueError, match="already exists"):
        user_service.register_user("dup@example.com", "Second", "pass")

def test_registration_still_works_for_new_emails():
    user_service.register_user("a@example.com", "A", "pass")
    user_service.register_user("b@example.com", "B", "pass")
    assert len(user_service._user_db) == 2