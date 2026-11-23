from datetime import UTC, datetime, timedelta

import jwt
from pwdlib import PasswordHash
from pwdlib.hashers.argon2 import Argon2Hasher


class Argon2PasswordHasher:
    def __init__(self) -> None:
        self._ph = PasswordHash((Argon2Hasher(),))

    def hash(self, password: str) -> str:
        return self._ph.hash(password)

    def verify(self, password: str, password_hash: str) -> bool:
        try:
            return self._ph.verify(password, password_hash)
        except Exception:  # malformed hash -> treat as failure
            return False


class JwtTokenService:
    def __init__(self, secret: str, ttl_minutes: int) -> None:
        self._secret, self._ttl = secret, timedelta(minutes=ttl_minutes)

    def issue(self, user_id: int) -> str:
        now = datetime.now(UTC)
        payload = {"sub": str(user_id), "iat": now, "exp": now + self._ttl}
        return jwt.encode(payload, self._secret, algorithm="HS256")

    def decode(self, token: str) -> int | None:
        try:
            return int(jwt.decode(token, self._secret, algorithms=["HS256"])["sub"])
        except (jwt.PyJWTError, KeyError, ValueError):
            return None
