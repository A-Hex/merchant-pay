from datetime import UTC, datetime, timedelta
from functools import cached_property
from uuid import uuid4

import jwt
from pwdlib import PasswordHash
from pwdlib.hashers.argon2 import Argon2Hasher

# A fixed, syntactically valid Argon2 hash used to equalise login timing when the
# account does not exist. Verifying against it costs the same as a real check, so an
# attacker cannot enumerate accounts by measuring response time.
_TIMING_DECOY_PASSWORD = "timing-equalisation-decoy"


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

    @cached_property
    def decoy_hash(self) -> str:
        """Argon2 hash of a random secret; verifying against it always fails."""
        return self.hash(f"{_TIMING_DECOY_PASSWORD}-{uuid4().hex}")


class JwtTokenService:
    """Stateless HS256 session tokens with issuer/audience/type binding.

    Decoding enforces ``iss``, ``aud``, ``typ`` and the required claims, so a token
    minted for another service (or another purpose) sharing the secret is rejected.
    """

    def __init__(self, secret: str, ttl_minutes: int, issuer: str = "merchant-pay",
                 audience: str = "merchant-pay-api") -> None:
        self._secret, self._ttl = secret, timedelta(minutes=ttl_minutes)
        self._issuer, self._audience = issuer, audience

    def issue(self, user_id: int, token_type: str = "access") -> str:
        now = datetime.now(UTC)
        payload = {
            "sub": str(user_id),
            "iat": now,
            "nbf": now,
            "exp": now + self._ttl,
            "iss": self._issuer,
            "aud": self._audience,
            "typ": token_type,
            "jti": uuid4().hex,
        }
        return jwt.encode(payload, self._secret, algorithm="HS256")

    def decode(self, token: str) -> int | None:
        try:
            payload = jwt.decode(
                token,
                self._secret,
                algorithms=["HS256"],
                audience=self._audience,
                issuer=self._issuer,
                options={"require": ["exp", "iat", "sub", "iss", "aud", "typ"]},
            )
            if payload.get("typ") != "access":
                return None
            return int(payload["sub"])
        except (jwt.PyJWTError, KeyError, TypeError, ValueError):
            return None
