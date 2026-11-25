"""Alert queries and state transitions. Loading -> aggregate method -> persist."""

from dataclasses import dataclass

from app.contexts.alerts.application.ports import AlertRepository
from app.contexts.alerts.domain.alert import Alert, AlertState
from app.shared.domain.errors import NotFound
from app.shared.domain.merchant_scope import MerchantScope


@dataclass(frozen=True, slots=True)
class AlertList:
    items: list[Alert]
    counts: dict[AlertState, int]


class ListAlerts:
    def __init__(self, repo: AlertRepository) -> None:
        self._repo = repo

    def execute(self, scope: MerchantScope, state: AlertState | None = None) -> AlertList:
        return AlertList(
            items=self._repo.list(scope, (state,) if state else None),
            counts=self._repo.count_by_state(scope),
        )


class _Transition:
    """Shared plumbing: the scope check is the authorization, the aggregate is the guard."""

    def __init__(self, repo: AlertRepository) -> None:
        self._repo = repo

    def _load(self, scope: MerchantScope, alert_id: int) -> Alert:
        alert = self._repo.get(scope, alert_id)
        if alert is None:
            raise NotFound("Alert not found")
        return alert

    def _apply(self, scope: MerchantScope, alert_id: int, transition: str) -> Alert:
        alert = self._load(scope, alert_id)
        getattr(alert, transition)()
        return self._repo.update(alert)


class AcknowledgeAlert(_Transition):
    def execute(self, scope: MerchantScope, alert_id: int) -> Alert:
        return self._apply(scope, alert_id, "acknowledge")


class ResolveAlert(_Transition):
    def execute(self, scope: MerchantScope, alert_id: int) -> Alert:
        return self._apply(scope, alert_id, "resolve")
