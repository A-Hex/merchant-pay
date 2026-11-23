from typing import Protocol

from app.contexts.identity.domain.model import Merchant, MerchantAccess, User


class UserRepository(Protocol):
    def get_by_email(self, email: str) -> User | None: ...

    def get(self, user_id: int) -> User | None: ...


class AccessRepository(Protocol):
    def for_user(self, user_id: int) -> list[MerchantAccess]: ...


class MerchantRepository(Protocol):
    def get(self, merchant_id: str) -> Merchant | None: ...


class PasswordHasher(Protocol):
    def hash(self, password: str) -> str: ...

    def verify(self, password: str, password_hash: str) -> bool: ...


class TokenService(Protocol):
    def issue(self, user_id: int) -> str: ...

    def decode(self, token: str) -> int | None: ...
