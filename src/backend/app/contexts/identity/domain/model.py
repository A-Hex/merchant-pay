from dataclasses import dataclass
from datetime import datetime
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


# ---- login history ---------------------------------------------------------------------------
class LoginOutcome(StrEnum):
    SUCCESS = "success"
    FAILURE = "failure"  # wrong password on an EXISTING account
    THROTTLED = "throttled"  # refused by the brute-force limiter
    LOGOUT = "logout"


@dataclass(frozen=True, slots=True)
class LoginEvent:
    user_id: int
    outcome: LoginOutcome
    occurred_at: datetime
    ip: str
    user_agent: str


LOGIN_HISTORY_RETENTION_DAYS = 90
_BROWSERS = (("Edg/", "Edge"), ("OPR/", "Opera"), ("Firefox/", "Firefox"), ("Chrome/", "Chrome"),
             ("Safari/", "Safari"))
_SYSTEMS = (("Android", "Android"), ("iPhone", "iOS"), ("iPad", "iPadOS"), ("Windows", "Windows"),
            ("Mac OS X", "macOS"), ("Linux", "Linux"))


def device_label(user_agent: str) -> str:
    """'Chrome · Linux' from a User-Agent; never more detail than browser family and OS."""
    browser = next((name for token, name in _BROWSERS if token in user_agent), None)
    system = next((name for token, name in _SYSTEMS if token in user_agent), None)
    if not browser and not system:
        return "unknown"
    return " · ".join(x for x in (browser, system) if x)
