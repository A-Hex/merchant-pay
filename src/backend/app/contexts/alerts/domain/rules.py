"""Alert rules (Strategy pattern). Add a rule = add a class; nothing else changes.

Rules are deterministic and auditable (blueprint §5): each explains metric, windows,
threshold and observed values. Statistical scores may prioritise, never change thresholds.
Every rule returns None when its sample is too small: no alert is better than a noisy one.
"""

import statistics
from dataclasses import dataclass
from datetime import date, timedelta
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
    month_to_date: list[Transaction] | None = None


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


@dataclass(frozen=True, slots=True)
class DeclineSpikeRule:
    """Decline rate in the current window against the previous window's decline rate.

    Fires when the rate is both relatively (x1.5) and absolutely (+5 points) worse,
    and only above a minimum attempt count; the explanation always shows the denominator.
    """

    code: str = "DECLINE_SPIKE"
    relative_threshold: Decimal = Decimal("1.5")
    absolute_points: Decimal = Decimal("0.05")
    min_attempts: int = 20

    def evaluate(self, ctx: RuleContext) -> Alert | None:
        cur, prev = compute_kpis(ctx.current), compute_kpis(ctx.previous)
        current_rate, baseline_rate = cur.decline_rate.value, prev.decline_rate.value
        if current_rate is None or baseline_rate is None:
            return None
        if (cur.decline_rate.denominator < self.min_attempts
                or prev.decline_rate.denominator < self.min_attempts):
            return None
        bar = max(baseline_rate * self.relative_threshold, baseline_rate + self.absolute_points)
        if current_rate < bar:
            return None
        severity = (Severity.CRITICAL if current_rate >= baseline_rate * 2 else Severity.WARNING)
        delta = (current_rate - baseline_rate) / baseline_rate if baseline_rate else None
        return Alert(
            merchant_id=ctx.merchant_id,
            rule_code=self.code,
            severity=severity,
            window=ctx.current_window,
            observed_value=current_rate,
            baseline_value=baseline_rate,
            delta_pct=delta,
            explanation=(
                f"Taux de refus {current_rate:.1%} ({cur.decline_rate.numerator} / "
                f"{cur.decline_rate.denominator} tentatives) du {ctx.current_window.start} au "
                f"{ctx.current_window.last_day}, contre {baseline_rate:.1%} "
                f"({prev.decline_rate.numerator} / {prev.decline_rate.denominator}) sur la période "
                f"précédente. Seuil : ×{self.relative_threshold} et au moins "
                f"+{self.absolute_points:.0%} de points, sur ≥ {self.min_attempts} tentatives."
            ),
            evidence_ref=f"status=declined&date_from={ctx.current_window.start}"
                         f"&date_to={ctx.current_window.last_day}",
        )


@dataclass(frozen=True, slots=True)
class InactivityRule:
    """Silence since the last transaction > 3x the merchant's own median gap between active days."""

    code: str = "INACTIVITY"
    multiplier: int = 3
    min_days: int = 3
    min_history: int = 10

    def evaluate(self, ctx: RuleContext) -> Alert | None:
        history = [t.occurred_at.date() for t in (*ctx.previous, *ctx.current)]
        if len(history) < self.min_history:
            return None
        active_days = sorted({d.toordinal() for d in history})
        gaps = [b - a for a, b in zip(active_days, active_days[1:], strict=False)]
        if not gaps:
            return None
        median_gap = statistics.median_low(gaps)
        last_day = date.fromordinal(active_days[-1])
        silence = (ctx.today - last_day).days
        threshold = max(self.min_days, median_gap * self.multiplier)
        if silence < threshold:
            return None
        severity = Severity.CRITICAL if silence >= threshold * 2 else Severity.WARNING
        return Alert(
            merchant_id=ctx.merchant_id,
            rule_code=self.code,
            severity=severity,
            window=ctx.current_window,
            observed_value=Decimal(silence),
            baseline_value=Decimal(median_gap),
            delta_pct=None,
            explanation=(
                f"Aucune transaction depuis {silence} jours (dernière le {last_day}). "
                f"Écart médian habituel entre deux jours d'activité : {median_gap} jour(s). "
                f"Seuil : {threshold} jours ({self.multiplier} × l'écart médian)."
            ),
            evidence_ref=f"date_from={last_day}&date_to={ctx.today}",
        )


@dataclass(frozen=True, slots=True)
class GoalReachedRule:
    """Month-to-date accepted collection crossing 80% then 100% of the monthly goal."""

    code: str = "GOAL_PROGRESS"
    warn_at: Decimal = Decimal("0.80")
    reached_at: Decimal = Decimal("1.00")

    def evaluate(self, ctx: RuleContext) -> Alert | None:
        goal = ctx.monthly_goal
        if goal is None or goal.centimes <= 0:
            return None
        month = ctx.month_to_date if ctx.month_to_date is not None else ctx.current
        collected = compute_kpis(month).gross_collected
        ratio = Decimal(collected.centimes) / Decimal(goal.centimes)
        if ratio < self.warn_at:
            return None
        reached = ratio >= self.reached_at
        return Alert(
            merchant_id=ctx.merchant_id,
            rule_code=self.code,
            severity=Severity.INFO,
            window=DateRange(ctx.today.replace(day=1), ctx.today + timedelta(days=1)),
            observed_value=collected.to_decimal(),
            baseline_value=goal.to_decimal(),
            delta_pct=ratio - 1,
            explanation=(
                f"Objectif mensuel {'atteint' if reached else 'bientôt atteint'} : "
                f"{ratio:.0%} au {ctx.today} ({collected.to_decimal()} DZD encaissés sur un "
                f"objectif de {goal.to_decimal()} DZD)."
            ),
            evidence_ref=f"status=accepted&date_from={ctx.today.replace(day=1)}&date_to={ctx.today}",
        )


DEFAULT_RULES: tuple[AlertRule, ...] = (
    CollectionDropRule(),
    DeclineSpikeRule(),
    InactivityRule(),
    GoalReachedRule(),
)
