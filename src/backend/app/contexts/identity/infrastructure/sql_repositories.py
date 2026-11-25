from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.contexts.identity.domain.model import (
    LOGIN_HISTORY_RETENTION_DAYS,
    LoginEvent,
    LoginOutcome,
    Merchant,
    MerchantAccess,
    Role,
    User,
    UserStatus,
)
from app.db.models import AuditEventRow, LoginEventRow, MerchantRow, UserMerchantAccessRow, UserRow
from app.shared.domain.errors import NotFound
from app.shared.domain.money import Money


def _user(row: UserRow) -> User:
    return User(row.id, row.email, row.password_hash, UserStatus(row.status))


class SqlUserRepository:
    def __init__(self, session: Session) -> None:
        self._s = session

    def get_by_email(self, email: str) -> User | None:
        row = self._s.scalar(select(UserRow).where(UserRow.email == email))
        return _user(row) if row else None

    def get(self, user_id: int) -> User | None:
        row = self._s.get(UserRow, user_id)
        return _user(row) if row else None


class SqlAccessRepository:
    def __init__(self, session: Session) -> None:
        self._s = session

    def for_user(self, user_id: int) -> list[MerchantAccess]:
        rows = self._s.scalars(
            select(UserMerchantAccessRow).where(UserMerchantAccessRow.user_id == user_id)
            .order_by(UserMerchantAccessRow.merchant_id)
        ).all()
        return [MerchantAccess(r.merchant_id, Role(r.role)) for r in rows]


class SqlMerchantRepository:
    def __init__(self, session: Session) -> None:
        self._s = session

    def get(self, merchant_id: str) -> Merchant | None:
        row = self._s.get(MerchantRow, merchant_id)
        if row is None:
            return None
        goal = Money(row.monthly_goal_centimes) if row.monthly_goal_centimes is not None else None
        days = tuple(d for d in row.operating_days.split(",") if d)
        return Merchant(row.merchant_id, row.display_name, row.category, row.timezone, days, goal)

    def save(self, merchant: Merchant) -> None:
        """Update in the request's unit of work; get_db() commits at the end of the request."""
        row = self._s.get(MerchantRow, merchant.merchant_id)
        if row is None:
            raise NotFound("Merchant not found")
        row.display_name = merchant.display_name
        row.category = merchant.category
        row.operating_days = ",".join(merchant.operating_days)
        row.monthly_goal_centimes = merchant.monthly_goal.centimes if merchant.monthly_goal else None
        self._s.flush()


class SqlAuditLog:
    def __init__(self, session: Session) -> None:
        self._s = session

    def record(self, actor_id: int, action: str, entity_ref: str) -> None:
        self._s.add(AuditEventRow(actor_id=actor_id, action=action, entity_ref=entity_ref[:255]))


class SqlLoginHistory:
    """Writes through its OWN short transaction, so a failed login (whose request rolls back) is
    still recorded. Prunes the user's events older than the retention window on each write."""

    def __init__(self, open_session: Callable[[], Session]) -> None:
        self._open = open_session

    def record(self, event: LoginEvent) -> None:
        cutoff = event.occurred_at - timedelta(days=LOGIN_HISTORY_RETENTION_DAYS)
        with self._open() as s, s.begin():
            s.add(LoginEventRow(user_id=event.user_id, outcome=event.outcome.value,
                                occurred_at=event.occurred_at, ip=event.ip, user_agent=event.user_agent))
            s.execute(delete(LoginEventRow).where(LoginEventRow.user_id == event.user_id,
                                                  LoginEventRow.occurred_at < cutoff))

    def recent(self, user_id: int, limit: int) -> list[LoginEvent]:
        with self._open() as s:
            rows = s.scalars(select(LoginEventRow).where(LoginEventRow.user_id == user_id)
                             .order_by(LoginEventRow.occurred_at.desc(), LoginEventRow.id.desc())
                             .limit(limit)).all()
            return [LoginEvent(r.user_id, LoginOutcome(r.outcome), _aware(r.occurred_at), r.ip, r.user_agent)
                    for r in rows]


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)  # SQLite drops the offset; Postgres keeps it
