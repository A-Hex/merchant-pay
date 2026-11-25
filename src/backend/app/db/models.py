"""ORM tables (infrastructure). Domain objects never import this module.

The full schema for all contexts is defined up front so the two developers never
create conflicting Alembic revisions on the hackathon day.
"""

from datetime import UTC, date, datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def _now() -> datetime:
    return datetime.now(UTC)


class MerchantRow(Base):
    __tablename__ = "merchants"
    merchant_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    display_name: Mapped[str] = mapped_column(String(200))
    category: Mapped[str] = mapped_column(String(100), default="")
    timezone: Mapped[str] = mapped_column(String(64), default="Africa/Algiers")
    operating_days: Mapped[str] = mapped_column(String(64), default="sun,mon,tue,wed,thu,sat")
    monthly_goal_centimes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)


class UserRow(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(20), default="active")


class UserMerchantAccessRow(Base):
    __tablename__ = "user_merchant_access"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    merchant_id: Mapped[str] = mapped_column(ForeignKey("merchants.merchant_id"), primary_key=True)
    role: Mapped[str] = mapped_column(String(20), default="owner")


class ImportBatchRow(Base):
    __tablename__ = "import_batches"
    batch_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    source_name: Mapped[str] = mapped_column(String(255))
    data_origin: Mapped[str] = mapped_column(String(32))
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    row_count: Mapped[int] = mapped_column(Integer)


class TransactionRow(Base):
    """The 7 original source fields + provenance metadata (data_origin, source_batch_id)."""

    __tablename__ = "transactions"
    transaction_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    merchant_id: Mapped[str] = mapped_column(ForeignKey("merchants.merchant_id"))
    occurred_at: Mapped[datetime] = mapped_column(DateTime)  # merchant-local time (Africa/Algiers)
    amount_centimes: Mapped[int] = mapped_column(BigInteger)
    channel: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(32))
    category: Mapped[str] = mapped_column(String(100))
    data_origin: Mapped[str] = mapped_column(String(32))
    source_batch_id: Mapped[str] = mapped_column(ForeignKey("import_batches.batch_id"))
    # optional pseudonymous merchant-scoped customer reference (enriched synthetic data only)
    customer_token: Mapped[str | None] = mapped_column(String(64), nullable=True)

    __table_args__ = (Index("ix_transactions_merchant_time", "merchant_id", "occurred_at"),
                      Index("ix_transactions_merchant_customer", "merchant_id", "customer_token"))


class AlertRow(Base):
    __tablename__ = "alerts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    merchant_id: Mapped[str] = mapped_column(ForeignKey("merchants.merchant_id"), index=True)
    rule_code: Mapped[str] = mapped_column(String(64))
    severity: Mapped[str] = mapped_column(String(16))
    window_start: Mapped[datetime] = mapped_column(Date)
    window_end: Mapped[datetime] = mapped_column(Date)
    observed_value: Mapped[float] = mapped_column(Numeric(20, 6))
    baseline_value: Mapped[float | None] = mapped_column(Numeric(20, 6), nullable=True)
    delta_pct: Mapped[float | None] = mapped_column(Numeric(12, 6), nullable=True)
    explanation: Mapped[str] = mapped_column(Text)
    evidence_ref: Mapped[str] = mapped_column(Text, default="")
    state: Mapped[str] = mapped_column(String(16), default="open")
    dedupe_key: Mapped[str] = mapped_column(String(255), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class ScenarioRunRow(Base):
    __tablename__ = "scenario_runs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    merchant_id: Mapped[str] = mapped_column(ForeignKey("merchants.merchant_id"), index=True)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    baseline_start: Mapped[datetime] = mapped_column(Date)
    baseline_end: Mapped[datetime] = mapped_column(Date)
    assumptions: Mapped[dict] = mapped_column(JSON)
    projected_count: Mapped[int] = mapped_column(Integer)
    projected_collection_centimes: Mapped[int] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class AuditEventRow(Base):
    __tablename__ = "audit_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    actor_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    action: Mapped[str] = mapped_column(String(64))
    entity_ref: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class CustomerActionRow(Base):
    """Append-only log of the merchant's win-back decisions; latest row per customer = current state."""

    __tablename__ = "customer_actions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    merchant_id: Mapped[str] = mapped_column(ForeignKey("merchants.merchant_id"))
    customer_token: Mapped[str] = mapped_column(String(64))
    action: Mapped[str] = mapped_column(String(16))  # dismiss | snooze | contacted | clear
    snooze_until: Mapped[date | None] = mapped_column(Date, nullable=True)
    actor_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    __table_args__ = (Index("ix_customer_actions_lookup", "merchant_id", "customer_token", "created_at"),)
