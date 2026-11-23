from typing import Protocol

from app.contexts.alerts.domain.alert import Alert
from app.shared.domain.merchant_scope import MerchantScope


class AlertRepository(Protocol):
    def list(self, scope: MerchantScope) -> list[Alert]: ...

    def get(self, scope: MerchantScope, alert_id: int) -> Alert | None: ...

    def save(self, alert: Alert) -> Alert:
        """Insert or update. Insert is skipped when dedupe_key already exists."""
        ...


# TODO(Person A):
#   application/evaluate_alerts.py: EvaluateAlerts(reader: TransactionReader, repo, rules)
#       .execute(scope, today) -> builds RuleContext (last 14 days vs previous 14), runs rules,
#       saves new alerts.
#   application/manage_alerts.py: ListAlerts, AcknowledgeAlert, ResolveAlert (load -> call
#       aggregate method -> save).
#   infrastructure/sql_alert_repository.py (AlertRow in app/db/models.py already exists).
#   api/router.py: GET /alerts, POST /alerts/evaluate, POST /alerts/{id}/acknowledge|resolve.
