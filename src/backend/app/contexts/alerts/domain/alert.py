"""Alert aggregate with an explicit state machine: open -> acknowledged -> resolved."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum

from app.shared.domain.date_range import DateRange
from app.shared.domain.errors import InvalidStateTransition


class AlertState(StrEnum):
    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"


class Severity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass(slots=True)
class Alert:
    merchant_id: str
    rule_code: str
    severity: Severity
    window: DateRange
    observed_value: Decimal
    baseline_value: Decimal | None
    delta_pct: Decimal | None
    explanation: str
    evidence_ref: str = ""
    state: AlertState = AlertState.OPEN
    id: int | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def dedupe_key(self) -> str:
        """Same rule + merchant + window => same alert. Re-evaluation is idempotent."""
        return f"{self.rule_code}:{self.merchant_id}:{self.window.start}:{self.window.end}"

    def acknowledge(self) -> None:
        if self.state is not AlertState.OPEN:
            raise InvalidStateTransition(f"Cannot acknowledge an alert in state {self.state}")
        self.state = AlertState.ACKNOWLEDGED

    def resolve(self) -> None:
        if self.state is AlertState.RESOLVED:
            raise InvalidStateTransition("Alert already resolved")
        self.state = AlertState.RESOLVED
