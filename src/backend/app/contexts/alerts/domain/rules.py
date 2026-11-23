"""Alert rules (Strategy pattern). Add a rule = add a class; nothing else changes.

Rules are deterministic and auditable (blueprint §5): each explains metric, windows,
threshold and observed values. Statistical scores may prioritise, never change thresholds.
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Protocol

from app.contexts.alerts.domain.alert import Alert, Severity
from app.contexts.analytics.domain.kpis import compute_kpis
from app.contexts.ledger.domain.transaction import Transaction
from app.shared.domain.date_range import DateRange
from app.shared.domain.money import Money


@dataclass(frozen=True, slots=True)
class RuleContext:
    merchant_id: str
    today: date
    current_window: DateRange
    previous_window: DateRange
    current: list[Transaction]
    previous: list[Transaction]
    monthly_goal: Money | None = None


class AlertRule(Protocol):
    code: str

    def evaluate(self, ctx: RuleContext) -> Alert | None: ...


@dataclass(frozen=True, slots=True)
class CollectionDropRule:
    """Accepted collection in current window <= previous window x threshold."""

    code: str = "COLLECTION_DROP"
    threshold: Decimal = Decimal("0.80")
    min_previous_accepted: int = 5  # minimum-sample gate: avoid noise on tiny histories

    def evaluate(self, ctx: RuleContext) -> Alert | None:
        cur, prev = compute_kpis(ctx.current), compute_kpis(ctx.previous)
        if prev.accepted_count < self.min_previous_accepted or prev.gross_collected.centimes == 0:
            return None
        if cur.gross_collected.centimes > prev.gross_collected.scale(self.threshold).centimes:
            return None
        current_amt, previous_amt = cur.gross_collected.to_decimal(), prev.gross_collected.to_decimal()
        delta = (current_amt - previous_amt) / previous_amt
        severity = Severity.CRITICAL if delta <= Decimal("-0.40") else Severity.WARNING
        return Alert(
            merchant_id=ctx.merchant_id,
            rule_code=self.code,
            severity=severity,
            window=ctx.current_window,
            observed_value=current_amt,
            baseline_value=previous_amt,
            delta_pct=delta,
            explanation=(
                f"Encaissements acceptés {current_amt} DZD du {ctx.current_window.start} au "
                f"{ctx.current_window.last_day}, contre {previous_amt} DZD sur la période "
                f"précédente ({delta:.1%}). Seuil : baisse ≥ {1 - self.threshold:.0%}."
            ),
            evidence_ref=f"status=accepted&date_from={ctx.current_window.start}"
                         f"&date_to={ctx.current_window.last_day}",
        )


# TODO(Person A): InactivityRule (no tx for N days, N > merchant's median gap x 3),
#   DeclineSpikeRule (decline rate vs baseline, show denominator, min attempts gate),
#   GoalReachedRule (accepted month-to-date >= 80% / 100% of monthly_goal).
DEFAULT_RULES: tuple[AlertRule, ...] = (CollectionDropRule(),)
