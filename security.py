import os
from pathlib import Path
from typing import Dict
import secrets
import json


class SecurityConfig:
    """Security configuration and hardening for production."""
    
    REQUIRED_ENV_VARS = [
        "SECRET_KEY",
        "FLASK_ENV",
    ]
    
    OPTIONAL_ENV_VARS = {
        "FLASK_ENV": "production",
        "DEBUG": "False",
        "ALLOWED_HOSTS": "localhost,127.0.0.1",
        "MAX_LOGIN_ATTEMPTS": "5",
        "LOGIN_TIMEOUT_MINUTES": "30",
        "SESSION_TIMEOUT_MINUTES": "60",
        "DATABASE_URL": "sqlite:///portfolio_history.db",
        "LOG_LEVEL": "INFO",
    }

    @staticmethod
    def generate_secrets() -> Dict[str, str]:
        """Generate secure secrets for production."""
        return {
            "SECRET_KEY": secrets.token_urlsafe(32),
            "JWT_SECRET": secrets.token_urlsafe(32),
            "CSRF_TOKEN_SECRET": secrets.token_urlsafe(32),
        }

    @staticmethod
    def create_env_template() -> str:
        """Create a template .env file for users."""
        return """# Crypto Gains Bot - Production Security Config
# NEVER commit this file to version control!
# NEVER share these secrets!

# Flask Configuration
FLASK_ENV=production
DEBUG=False
SECRET_KEY=YOUR_SECRET_KEY_HERE
JWT_SECRET=YOUR_JWT_SECRET_HERE
CSRF_TOKEN_SECRET=YOUR_CSRF_TOKEN_HERE

# Server Configuration
ALLOWED_HOSTS=localhost,127.0.0.1
SERVER_PORT=5000
SERVER_HOST=127.0.0.1

# Database Configuration
DATABASE_URL=sqlite:///portfolio_history.db
DATABASE_BACKUP_PATH=/backups/portfolio_history.db

# Session & Authentication
MAX_LOGIN_ATTEMPTS=5
LOGIN_TIMEOUT_MINUTES=30
SESSION_TIMEOUT_MINUTES=60
SECURE_COOKIES=True
HTTPONLY_COOKIES=True
SAMESITE_COOKIES=Strict

# Logging
LOG_LEVEL=INFO
LOG_FILE=/var/log/crypto-gains/app.log

# Alert Credentials (Optional - keep secure!)
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
DISCORD_WEBHOOK_URL=
SMTP_SERVER=
SMTP_USERNAME=
SMTP_PASSWORD=
ALERT_EMAIL_RECIPIENTS=

# API Rate Limiting
RATE_LIMIT_ENABLED=True
RATE_LIMIT_REQUESTS=100
RATE_LIMIT_WINDOW=3600

# HTTPS/TLS (for reverse proxy)
USE_HTTPS=True
SSL_CERT_PATH=
SSL_KEY_PATH=
"""

    @staticmethod
    def load_env() -> Dict[str, str]:
        """Load environment variables securely."""
        from dotenv import load_dotenv
        
        env_path = Path(".env")
        if not env_path.exists():
            raise FileNotFoundError(
                ".env file not found. Create one using the template at .env.example"
            )
        
        load_dotenv(env_path)
        
        # Verify required vars are set
        for var in SecurityConfig.REQUIRED_ENV_VARS:
            if not os.getenv(var):
                raise ValueError(f"Missing required environment variable: {var}")
        
        return dict(os.environ)

    @staticmethod
    def create_env_example():
        """Create .env.example file for users."""
        template = SecurityConfig.create_env_template()
        with open(".env.example", "w") as f:
            f.write(template)
        print("✅ Created .env.example - Copy to .env and fill in your values")


class EncryptionHelper:
    """Helper for encrypting sensitive data at rest."""
    
    @staticmethod
    def encrypt_api_key(api_key: str, master_key: str) -> str:
        """Encrypt API key using master key."""
        from cryptography.fernet import Fernet
        import base64
        
        # Derive a key from master_key
        key = base64.urlsafe_b64encode(master_key.encode().ljust(32)[:32])
        f = Fernet(key)
        return f.encrypt(api_key.encode()).decode()

    @staticmethod
    def decrypt_api_key(encrypted_key: str, master_key: str) -> str:
        """Decrypt API key using master key."""
        from cryptography.fernet import Fernet
        import base64
        
        key = base64.urlsafe_b64encode(master_key.encode().ljust(32)[:32])
        f = Fernet(key)
        return f.decrypt(encrypted_key.encode()).decode()


class InputValidator:
    """Validate and sanitize user inputs."""
    
    @staticmethod
    def validate_username(username: str) -> bool:
        """Validate username format."""
        import re
        # Alphanumeric + underscore, 3-32 chars
        return bool(re.match(r"^[a-zA-Z0-9_]{3,32}$", username))

    @staticmethod
    def validate_password(password: str) -> tuple:
        """Validate password strength."""
        import re
        
        errors = []
        
        if len(password) < 12:
            errors.append("Password must be at least 12 characters")
        
        if not re.search(r"[A-Z]", password):
            errors.append("Password must contain uppercase letters")
        
        if not re.search(r"[a-z]", password):
            errors.append("Password must contain lowercase letters")
        
        if not re.search(r"[0-9]", password):
            errors.append("Password must contain numbers")
        
        if not re.search(r"[!@#$%^&*()_+\-=\[\]{};:',.<>?/`~]", password):
            errors.append("Password must contain special characters")
        
        return len(errors) == 0, errors

    @staticmethod
    def validate_email(email: str) -> bool:
        """Validate email format."""
        import re
        pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        return bool(re.match(pattern, email))

    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """Sanitize filename to prevent directory traversal."""
        import re
        # Remove path separators and special chars
        sanitized = re.sub(r"[^a-zA-Z0-9._-]", "", filename)
        return sanitized or "export"

    @staticmethod
    def validate_json_input(data: str, max_size: int = 1048576) -> bool:
        """Validate JSON input size and format."""
        if len(data) > max_size:
            raise ValueError(f"Input exceeds maximum size of {max_size} bytes")
        
        try:
            json.loads(data)
            return True
        except json.JSONDecodeError:
            return False


class RateLimiter:
    """Simple rate limiting for API endpoints."""
    
    def __init__(self, max_requests: int = 100, window_seconds: int = 3600):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests = {}

    def is_allowed(self, identifier: str) -> bool:
        """Check if request is allowed."""
        import time
        current_time = time.time()
        
        if identifier not in self.requests:
            self.requests[identifier] = []
        
        # Remove old requests outside the window
        self.requests[identifier] = [
            req_time for req_time in self.requests[identifier]
            if current_time - req_time < self.window_seconds
        ]
        
        if len(self.requests[identifier]) < self.max_requests:
            self.requests[identifier].append(current_time)
            return True
        
        return False

    def get_remaining(self, identifier: str) -> int:
        """Get remaining requests for identifier."""
        import time
        current_time = time.time()
        
        if identifier not in self.requests:
            return self.max_requests
        
        # Remove old requests
        self.requests[identifier] = [
            req_time for req_time in self.requests[identifier]
            if current_time - req_time < self.window_seconds
        ]
        
        return max(0, self.max_requests - len(self.requests[identifier]))


class SecurityHeaders:
    """Generate secure HTTP headers."""
    
    @staticmethod
    def get_security_headers() -> Dict[str, str]:
        """Return security headers for Flask responses."""
        return {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "X-XSS-Protection": "1; mode=block",
            "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
            "Content-Security-Policy": "default-src 'self'; script-src 'self' https://cdn.jsdelivr.net; style-src 'self' 'unsafe-inline'",
            "Referrer-Policy": "strict-origin-when-cross-origin",
            "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
        }

    @staticmethod
    def apply_to_flask(app) -> None:
        """Apply security headers to Flask app."""
        @app.after_request
        def set_security_headers(response):
            for header, value in SecurityHeaders.get_security_headers().items():
                response.headers[header] = value
            return response
