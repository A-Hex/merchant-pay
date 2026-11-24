from datetime import date, datetime

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from app.container import (
    get_acknowledge_alert,
    get_evaluate_alerts,
    get_list_alerts,
    get_resolve_alert,
    get_scope,
    get_today,
)
from app.contexts.alerts.application.evaluate_alerts import EvaluateAlerts
from app.contexts.alerts.application.manage_alerts import (
    AcknowledgeAlert,
    ListAlerts,
    ResolveAlert,
)
from app.contexts.alerts.domain.alert import Alert, AlertState, Severity
from app.shared.api.schemas import PeriodOut
from app.shared.domain.merchant_scope import MerchantScope

router = APIRouter(prefix="/alerts", tags=["alerts"])

# What observed_value / baseline_value mean, so the UI formats them without second-guessing.
_UNITS = {
    "COLLECTION_DROP": "amount",
    "GOAL_PROGRESS": "amount",
    "DECLINE_SPIKE": "rate",
    "INACTIVITY": "days",
}


class AlertOut(BaseModel):
    id: int
    rule_code: str
    severity: Severity
    state: AlertState
    unit: str
    window: PeriodOut
    observed_value: str  # exact decimal, display only
    baseline_value: str | None
    delta_pct: float | None
    explanation: str
    evidence_ref: str
    created_at: datetime

    @classmethod
    def of(cls, a: Alert) -> "AlertOut":
        return cls(
            id=a.id or 0,
            rule_code=a.rule_code,
            severity=a.severity,
            state=a.state,
            unit=_UNITS.get(a.rule_code, "number"),
            window=PeriodOut.of(a.window),
            observed_value=f"{a.observed_value:.6f}".rstrip("0").rstrip("."),
            baseline_value=(f"{a.baseline_value:.6f}".rstrip("0").rstrip(".")
                            if a.baseline_value is not None else None),
            delta_pct=float(a.delta_pct) if a.delta_pct is not None else None,
            explanation=a.explanation,
            evidence_ref=a.evidence_ref,
            created_at=a.created_at,
        )


class AlertPageOut(BaseModel):
    items: list[AlertOut]
    counts: dict[str, int]


class EvaluationOut(BaseModel):
    created: list[AlertOut]
    current_period: PeriodOut
    previous_period: PeriodOut


@router.get("", response_model=AlertPageOut)
def list_alerts(
    state: AlertState | None = None,
    limit: int = Query(default=200, ge=1, le=500),
    scope: MerchantScope = Depends(get_scope),
    uc: ListAlerts = Depends(get_list_alerts),
) -> AlertPageOut:
    result = uc.execute(scope, state)
    return AlertPageOut(
        items=[AlertOut.of(a) for a in result.items[:limit]],
        counts={s.value: n for s, n in result.counts.items()},
    )


@router.post("/evaluate", response_model=EvaluationOut)
def evaluate_alerts(
    scope: MerchantScope = Depends(get_scope),
    today: date = Depends(get_today),
    uc: EvaluateAlerts = Depends(get_evaluate_alerts),
) -> EvaluationOut:
    result = uc.execute(scope, today)
    return EvaluationOut(
        created=[AlertOut.of(a) for a in result.created],
        current_period=PeriodOut.of(result.current_window),
        previous_period=PeriodOut.of(result.previous_window),
    )


@router.post("/{alert_id}/acknowledge", response_model=AlertOut)
def acknowledge_alert(alert_id: int, scope: MerchantScope = Depends(get_scope),
                      uc: AcknowledgeAlert = Depends(get_acknowledge_alert)) -> AlertOut:
    return AlertOut.of(uc.execute(scope, alert_id))


@router.post("/{alert_id}/resolve", response_model=AlertOut)
def resolve_alert(alert_id: int, scope: MerchantScope = Depends(get_scope),
                  uc: ResolveAlert = Depends(get_resolve_alert)) -> AlertOut:
    return AlertOut.of(uc.execute(scope, alert_id))
