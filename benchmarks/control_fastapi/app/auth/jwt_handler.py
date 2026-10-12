"""
Control FastAPI Project - Authentication
Manual JWT implementation for benchmarking against SwX.
"""

from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
import secrets

SECRET_KEY = "control-project-secret-key-change-in-production"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60
REFRESH_TOKEN_EXPIRE_DAYS = 30

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against a hash."""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hash a password."""
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire, "iat": datetime.utcnow()})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def create_refresh_token(data: dict) -> str:
    """Create a refresh token."""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh"})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> Optional[dict]:
    """Decode and validate a JWT token."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None


class TokenPayload:
    """Token payload structure."""
    def __init__(self, sub: str, exp: datetime, iat: datetime, aud: str = None, type: str = "access"):
        self.sub = sub  # subject (user_id)
        self.exp = exp  # expiration
        self.iat = iat  # issued at
        self.aud = aud  # audience
        self.type = type  # token type
    
    @classmethod
    def from_dict(cls, data: dict) -> "TokenPayload":
        return cls(
            sub=data.get("sub"),
            exp=datetime.fromtimestamp(data.get("exp", 0)),
            iat=datetime.fromtimestamp(data.get("iat", 0)),
            aud=data.get("aud"),
            type=data.get("type", "access")
        )


class TokenBlacklist:
    """Simple in-memory token blacklist."""
    def __init__(self):
        self._blacklist = set()
    
    def add(self, jti: str) -> None:
        """Add token ID to blacklist."""
        self._blacklist.add(jti)
    
    def is_blacklisted(self, jti: str) -> bool:
        """Check if token is blacklisted."""
        return jti in self._blacklist
    
    def remove(self, jti: str) -> None:
        """Remove from blacklist."""
        self._blacklist.discard(jti)


# Global blacklist instance
token_blacklist = TokenBlacklist()


def revoke_token(jti: str) -> None:
    """Revoke a token by adding to blacklist."""
    token_blacklist.add(jti)


def is_token_revoked(jti: str) -> bool:
    """Check if token has been revoked."""
    return token_blacklist.is_blacklisted(jti)


def generate_api_key() -> str:
    """Generate a random API key."""
    return f"sk_{secrets.token_urlsafe(32)}"


def hash_api_key(api_key: str) -> str:
    """Hash an API key for storage."""
    return pwd_context.hash(api_key)
