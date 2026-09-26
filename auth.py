import hashlib
import secrets
from pathlib import Path
import json
from typing import Optional, Dict


class AuthManager:
    def __init__(self, users_path: str = "users.json"):
        self.users_path = Path(users_path)
        self.users = self.load_users()

    def load_users(self) -> Dict:
        if self.users_path.exists():
            with open(self.users_path, "r") as f:
                return json.load(f)
        return {}

    def save_users(self) -> None:
        with open(self.users_path, "w") as f:
            json.dump(self.users, f, indent=2)

    @staticmethod
    def hash_password(password: str, salt: str = None) -> tuple:
        """Hash password with salt."""
        if salt is None:
            salt = secrets.token_hex(16)
        hashed = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100000)
        return hashed.hex(), salt

    def register_user(self, username: str, password: str, email: str = "") -> bool:
        """Register a new user."""
        if username in self.users:
            print(f"❌ User '{username}' already exists")
            return False

        hashed_password, salt = self.hash_password(password)
        self.users[username] = {
            "password_hash": hashed_password,
            "salt": salt,
            "email": email,
            "created_at": str(__import__("datetime").datetime.now()),
            "portfolio_path": f"portfolios/{username}_portfolio.json"
        }
        self.save_users()
        print(f"✅ User '{username}' registered successfully")
        return True

    def verify_password(self, username: str, password: str) -> bool:
        """Verify user password."""
        if username not in self.users:
            return False

        user = self.users[username]
        hashed_password, _ = self.hash_password(password, user["salt"])
        return hashed_password == user["password_hash"]

    def authenticate(self, username: str, password: str) -> Optional[str]:
        """Authenticate user and return token."""
        if not self.verify_password(username, password):
            print(f"❌ Authentication failed for '{username}'")
            return None

        token = secrets.token_urlsafe(32)
        self.users[username]["token"] = token
        self.users[username]["token_created"] = str(__import__("datetime").datetime.now())
        self.save_users()
        print(f"✅ User '{username}' authenticated")
        return token

    def verify_token(self, username: str, token: str) -> bool:
        """Verify authentication token."""
        if username not in self.users:
            return False

        user = self.users[username]
        stored_token = user.get("token")
        return stored_token == token

    def get_user_portfolio_path(self, username: str) -> Optional[str]:
        """Get portfolio path for user."""
        if username in self.users:
            return self.users[username].get("portfolio_path")
        return None

    def delete_user(self, username: str) -> bool:
        """Delete a user account."""
        if username not in self.users:
            return False

        del self.users[username]
        self.save_users()
        print(f"✅ User '{username}' deleted")
        return True

    def list_users(self) -> list:
        """List all users."""
        return list(self.users.keys())
