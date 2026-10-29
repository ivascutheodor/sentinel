import hashlib
import re
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

_hasher = PasswordHasher()

# Shared by the API schemas and the `create_user` CLI. The maximum stops a huge "password"
# from making Argon2 burn CPU on every attempt.
MIN_PASSWORD_LENGTH = 12
MAX_PASSWORD_LENGTH = 1024
# Same rule as the `users.username` CHECK.
USERNAME_PATTERN = re.compile(r"^[a-z0-9._-]{3,50}$")

# Checked against when the username is unknown, so a failed login takes the same
# time whether or not the account exists.
_DUMMY_HASH = _hasher.hash("sentinel-dummy-password")


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


def verify_dummy_password(password: str) -> None:
    verify_password(_DUMMY_HASH, password)


def password_needs_rehash(password_hash: str) -> bool:
    return _hasher.check_needs_rehash(password_hash)


def new_session_token() -> str:
    return secrets.token_urlsafe(32)


def hash_session_token(token: str) -> bytes:
    """Only this 32-byte digest is stored, so a database leak exposes no usable cookie."""
    return hashlib.sha256(token.encode()).digest()
