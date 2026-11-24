from dataclasses import dataclass
from enum import StrEnum

from app.shared.domain.errors import DomainError
from app.shared.domain.money import Money

WEEKDAYS: tuple[str, ...] = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")


class UserStatus(StrEnum):
    ACTIVE = "active"
    DISABLED = "disabled"


class Role(StrEnum):
    OWNER = "owner"
    STAFF = "staff"


#: Roles allowed to mutate merchant-level settings. Staff keeps read access only.
PROFILE_EDITOR_ROLES = frozenset({Role.OWNER})


def can_edit_profile(role: Role) -> bool:
    return role in PROFILE_EDITOR_ROLES


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


@dataclass(frozen=True, slots=True)
class MerchantChanges:
    """Partial merchant update, already validated by the API schema.

    ``monthly_goal_provided`` distinguishes "leave the goal alone" (False) from
    "clear the goal" (True with ``monthly_goal_centimes=None``).
    """

    display_name: str | None = None
    category: str | None = None
    operating_days: tuple[str, ...] | None = None
    monthly_goal_centimes: int | None = None
    monthly_goal_provided: bool = False

    def __post_init__(self) -> None:
        if self.display_name is not None and not (1 <= len(self.display_name.strip()) <= 200):
            raise DomainError("display_name must be between 1 and 200 characters")
        if self.category is not None and not (1 <= len(self.category.strip()) <= 100):
            raise DomainError("category must be between 1 and 100 characters")
        if self.operating_days is not None:
            days = self.operating_days
            if not days:
                raise DomainError("operating_days must contain at least one day")
            unknown = [d for d in days if d not in WEEKDAYS]
            if unknown:
                raise DomainError(f"Unknown operating day(s): {', '.join(unknown)}")
            if len(set(days)) != len(days):
                raise DomainError("operating_days must not contain duplicates")
        if self.monthly_goal_centimes is not None and self.monthly_goal_centimes < 0:
            raise DomainError("monthly_goal must not be negative")

    @property
    def is_empty(self) -> bool:
        return (self.display_name is None and self.category is None
                and self.operating_days is None and not self.monthly_goal_provided)
