from typing import Protocol

from app.contexts.identity.domain.model import Merchant, MerchantAccess, MerchantChanges, User


class UserRepository(Protocol):
    def get_by_email(self, email: str) -> User | None: ...

    def get(self, user_id: int) -> User | None: ...


class AccessRepository(Protocol):
    def for_user(self, user_id: int) -> list[MerchantAccess]: ...


class MerchantRepository(Protocol):
    def get(self, merchant_id: str) -> Merchant | None: ...

    def update(self, merchant_id: str, changes: MerchantChanges) -> Merchant | None:
        """Apply a partial update and return the refreshed aggregate, or None if missing."""
        ...


class PasswordHasher(Protocol):
    def hash(self, password: str) -> str: ...

    def verify(self, password: str, password_hash: str) -> bool: ...

    @property
    def decoy_hash(self) -> str:
        """A real hash that never matches; used to keep login timing constant."""
        ...


class LoginThrottle(Protocol):
    """Per-IP and per-account attempt limiter (application port)."""

    def ensure_allowed(self, client_ip: str, email: str) -> None: ...

    def record_failure(self, client_ip: str, email: str) -> None: ...

    def record_success(self, client_ip: str, email: str) -> None: ...


class TokenService(Protocol):
    def issue(self, user_id: int, token_type: str = "access") -> str: ...

    def decode(self, token: str) -> int | None: ...
