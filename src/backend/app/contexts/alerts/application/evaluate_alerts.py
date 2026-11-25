"""Run every alert rule over the last 14 days vs the 14 days before, and persist new alerts.

Deterministic and idempotent: re-evaluating the same window creates no duplicate (dedupe_key).
"""

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Protocol

from app.contexts.alerts.application.ports import AlertRepository, MerchantProfileReader
from app.contexts.alerts.domain.alert import Alert
from app.contexts.alerts.domain.rules import DEFAULT_RULES, AlertRule, RuleContext
from app.contexts.ledger.domain.transaction import Transaction
from app.shared.domain.date_range import DateRange
from app.shared.domain.merchant_scope import MerchantScope


class TransactionReader(Protocol):
    """Port. Implemented by ledger's SqlTransactionRepository (structural typing)."""

    def list_in_period(self, scope: MerchantScope, period: DateRange) -> list[Transaction]: ...


@dataclass(frozen=True, slots=True)
class EvaluationResult:
    created: list[Alert]
    current_window: DateRange
    previous_window: DateRange


class EvaluateAlerts:
    def __init__(self, reader: TransactionReader, alerts: AlertRepository,
                 merchants: MerchantProfileReader, rules: tuple[AlertRule, ...] = DEFAULT_RULES,
                 window_days: int = 14) -> None:
        self._reader = reader
        self._alerts = alerts
        self._merchants = merchants
        self._rules = rules
        self._window_days = window_days

    def execute(self, scope: MerchantScope, today: date) -> EvaluationResult:
        current = DateRange.last_n_days(today, self._window_days)
        previous = current.previous()
        month_to_date = DateRange(today.replace(day=1), today + timedelta(days=1))
        merchant = self._merchants.get(scope.merchant_id)
        ctx = RuleContext(
            merchant_id=scope.merchant_id,
            today=today,
            current_window=current,
            previous_window=previous,
            current=self._reader.list_in_period(scope, current),
            previous=self._reader.list_in_period(scope, previous),
            monthly_goal=merchant.monthly_goal if merchant else None,
            month_to_date=self._reader.list_in_period(scope, month_to_date),
        )
        created = []
        for rule in self._rules:
            alert = rule.evaluate(ctx)
            if alert is None:
                continue
            stored = self._alerts.add_if_absent(alert)
            if stored is not None:
                created.append(stored)
        return EvaluationResult(created, current, previous)
