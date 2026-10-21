import hashlib
import secrets
from functools import lru_cache

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError


class ArgonPasswordHasher:
    def __init__(self) -> None:
        self._hasher = PasswordHasher(time_cost=2, memory_cost=19456, parallelism=1)
        self._dummy = self._hasher.hash(secrets.token_urlsafe(32))

    def hash(self, password: str) -> str:
        return self._hasher.hash(password)

    def verify(self, password: str, password_hash: str | None) -> bool:
        try:
            valid = self._hasher.verify(password_hash or self._dummy, password)
            return valid and password_hash is not None
        except (InvalidHashError, VerificationError):
            return False


@lru_cache
def get_password_hasher() -> ArgonPasswordHasher:
    return ArgonPasswordHasher()


def token_digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def csrf_token(token: str) -> str:
    # Public anti-CSRF value cannot be used to recover the session credential.
    return hashlib.sha256(b"csrf:" + token.encode()).hexdigest()
