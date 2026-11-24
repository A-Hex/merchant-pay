"""SQLAlchemy adapter for the alerts context. Dedupe is enforced in the DB (unique dedupe_key)."""

from collections.abc import Sequence
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.contexts.alerts.domain.alert import Alert, AlertState, Severity
from app.db.models import AlertRow
from app.shared.domain.date_range import DateRange
from app.shared.domain.errors import DomainError, NotFound
from app.shared.domain.merchant_scope import MerchantScope

_SEVERITY_RANK = {"critical": 0, "warning": 1, "info": 2}


def _to_domain(row: AlertRow) -> Alert:
    return Alert(
        merchant_id=row.merchant_id,
        rule_code=row.rule_code,
        severity=Severity(row.severity),
        window=DateRange(row.window_start, row.window_end),
        observed_value=Decimal(row.observed_value),
        baseline_value=Decimal(row.baseline_value) if row.baseline_value is not None else None,
        delta_pct=Decimal(row.delta_pct) if row.delta_pct is not None else None,
        explanation=row.explanation,
        evidence_ref=row.evidence_ref,
        state=AlertState(row.state),
        id=row.id,
        created_at=row.created_at,
    )


class SqlAlertRepository:
    def __init__(self, session: Session) -> None:
        self._s = session

    def list(self, scope: MerchantScope, states: Sequence[AlertState] | None = None,
             limit: int | None = None) -> list[Alert]:
        stmt = select(AlertRow).where(AlertRow.merchant_id == scope.merchant_id)
        if states:
            stmt = stmt.where(AlertRow.state.in_([s.value for s in states]))
        severity_rank = case(_SEVERITY_RANK, value=AlertRow.severity, else_=len(_SEVERITY_RANK))
        stmt = stmt.order_by(severity_rank, AlertRow.created_at.desc(), AlertRow.id.desc())
        if limit is not None:
            stmt = stmt.limit(limit)
        return [_to_domain(r) for r in self._s.scalars(stmt).all()]

    def get(self, scope: MerchantScope, alert_id: int) -> Alert | None:
        row = self._s.get(AlertRow, alert_id)
        if row is None or row.merchant_id != scope.merchant_id:
            return None
        return _to_domain(row)

    def count_by_state(self, scope: MerchantScope) -> dict[AlertState, int]:
        rows = self._s.execute(
            select(AlertRow.state, func.count())
            .where(AlertRow.merchant_id == scope.merchant_id)
            .group_by(AlertRow.state)
        ).all()
        counts = {s: 0 for s in AlertState}
        for state, count in rows:
            counts[AlertState(state)] = count
        return counts

    def add_if_absent(self, alert: Alert) -> Alert | None:
        existing = self._s.scalar(select(AlertRow).where(AlertRow.dedupe_key == alert.dedupe_key))
        if existing is not None:
            return None
        row = AlertRow(
            merchant_id=alert.merchant_id,
            rule_code=alert.rule_code,
            severity=alert.severity.value,
            window_start=alert.window.start,
            window_end=alert.window.end,
            observed_value=alert.observed_value,
            baseline_value=alert.baseline_value,
            delta_pct=alert.delta_pct,
            explanation=alert.explanation,
            evidence_ref=alert.evidence_ref,
            state=alert.state.value,
            dedupe_key=alert.dedupe_key,
        )
        self._s.add(row)
        self._s.flush()
        return _to_domain(row)

    def update(self, alert: Alert) -> Alert:
        if alert.id is None:
            raise DomainError("Cannot update an alert that was never saved")
        row = self._s.get(AlertRow, alert.id)
        if row is None or row.merchant_id != alert.merchant_id:
            raise NotFound("Alert not found")
        row.state = alert.state.value
        row.updated_at = datetime.now(UTC)
        self._s.flush()
        return _to_domain(row)
