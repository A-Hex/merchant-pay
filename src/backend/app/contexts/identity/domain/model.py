from dataclasses import dataclass
from enum import StrEnum

from app.shared.domain.money import Money


class UserStatus(StrEnum):
    ACTIVE = "active"
    DISABLED = "disabled"


class Role(StrEnum):
    OWNER = "owner"
    STAFF = "staff"


@dataclass(frozen=True, slots=True)
class User:
    id: int
    email: str
    password_hash: str
    status: UserStatus

    @property
    def is_active(self) -> bool:
        return self.status is UserStatus.ACTIVE


@dataclass(frozen=True, slots=True)
class MerchantAccess:
    merchant_id: str
    role: Role


@dataclass(frozen=True, slots=True)
class Merchant:
    merchant_id: str
    display_name: str
    category: str
    timezone: str
    operating_days: tuple[str, ...]
    monthly_goal: Money | None
