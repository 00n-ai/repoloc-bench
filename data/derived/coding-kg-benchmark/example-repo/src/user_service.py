"""User service module — handles user registration, authentication, and profile management."""

from typing import Optional, Dict, List
from datetime import datetime
import hashlib
import json
import os

# In a real system this would be a database connection
_user_db: Dict[str, dict] = {}

# ─── User Models ───

class User:
    """Represents a registered user."""
    def __init__(self, user_id: str, email: str, name: str, role: str = "member"):
        self.user_id = user_id
        self.email = self._validate_email(email)
        self.name = name
        self.role = role
        self.created_at = datetime.utcnow()
        self.last_login: Optional[datetime] = None
        self.password_hash: Optional[str] = None

    @staticmethod
    def _validate_email(email: str) -> str:
        """Basic email validation."""
        if "@" not in email:
            raise ValueError(f"Invalid email: {email}")
        return email.lower()

    def to_dict(self) -> dict:
        """Serialize user to dictionary."""
        return {
            "user_id": self.user_id,
            "email": self.email,
            "name": self.name,
            "role": self.role,
            "created_at": self.created_at.isoformat(),
            "last_login": self.last_login.isoformat() if self.last_login else None,
        }

    def __repr__(self):
        return f"User(id={self.user_id}, email={self.email}, role={self.role})"


class AdminUser(User):
    """Admin user with elevated permissions."""
    def __init__(self, user_id: str, email: str, name: str):
        super().__init__(user_id, email, name, role="admin")
        self.permissions: List[str] = ["read", "write", "delete"]

    def has_permission(self, action: str) -> bool:
        """Check if admin has a permission."""
        return action in self.permissions

    def to_dict(self) -> dict:
        base = super().to_dict()
        base["permissions"] = self.permissions
        return base


# ─── Password Hashing ───

def hash_password(password: str) -> str:
    """Hash a password using SHA-256 with salt."""
    salt = os.urandom(16).hex()
    hashed = hashlib.sha256((password + salt).encode()).hexdigest()
    return f"{salt}${hashed}"


def verify_password(password: str, stored_hash: str) -> bool:
    """Verify a password against a stored salt$hash string."""
    try:
        salt, hashed = stored_hash.split("$")
        test_hash = hashlib.sha256((password + salt).encode()).hexdigest()
        return test_hash == hashed
    except ValueError:
        return False


# ─── User Service Functions ───

def register_user(email: str, name: str, password: str) -> User:
    """Register a new user. Raises ValueError if email already exists."""
    normalized_email = email.lower()
    for existing in _user_db.values():
        if existing.email == normalized_email:
            raise ValueError(f"User with email {email} already exists")
    user_id = f"user_{len(_user_db) + 1}"
    user = User(user_id, email, name)
    user.password_hash = hash_password(password)
    _user_db[user_id] = user
    return user


def authenticate_user(email: str, password: str) -> Optional[User]:
    """Authenticate a user by email and password. Returns User if valid, None otherwise."""
    for user in _user_db.values():
        if user.email == email.lower():
            if user.password_hash and verify_password(password, user.password_hash):
                user.last_login = datetime.utcnow()
                return user
    return None


def get_user_profile(user_id: str) -> Optional[dict]:
    """Get a user's profile as a dictionary. Returns None if user not found."""
    user = _user_db.get(user_id)
    if user:
        return user.to_dict()
    return None


def update_user_profile(user_id: str, name: Optional[str] = None, email: Optional[str] = None) -> Optional[User]:
    """Update a user's profile. Only provided fields are updated."""
    user = _user_db.get(user_id)
    if not user:
        return None
    if name:
        user.name = name
    if email:
        user.email = User._validate_email(email)
    return user


def list_users_by_role(role: str) -> List[User]:
    """List all users with a given role."""
    return [u for u in _user_db.values() if u.role == role]


def delete_user(user_id: str) -> bool:
    """Delete a user by ID. Returns True if deleted, False if not found."""
    if user_id in _user_db:
        del _user_db[user_id]
        return True
    return False


def promote_to_admin(user_id: str) -> Optional[AdminUser]:
    """Promote a regular user to admin. Returns new AdminUser or None if user not found."""
    user = _user_db.get(user_id)
    if not user:
        return None
    admin = AdminUser(user.user_id, user.email, user.name)
    admin.password_hash = user.password_hash
    admin.created_at = user.created_at
    admin.last_login = user.last_login
    _user_db[user_id] = admin
    return admin