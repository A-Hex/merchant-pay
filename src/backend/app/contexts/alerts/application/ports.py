from collections.abc import Sequence
from typing import Protocol

from app.contexts.alerts.domain.alert import Alert, AlertState
from app.contexts.identity.domain.model import Merchant
from app.shared.domain.merchant_scope import MerchantScope


class AlertRepository(Protocol):
    def list(self, scope: MerchantScope, states: Sequence[AlertState] | None = None,
             limit: int | None = None) -> list[Alert]:
        """Newest first, most severe first. Alerts of other merchants never leak in."""
        ...

    def get(self, scope: MerchantScope, alert_id: int) -> Alert | None: ...

    def count_by_state(self, scope: MerchantScope) -> dict[AlertState, int]: ...

    def add_if_absent(self, alert: Alert) -> Alert | None:
        """Insert a new alert. Returns None when its dedupe_key already exists (idempotent)."""
        ...

    def update(self, alert: Alert) -> Alert:
        """Persist a state change on an existing alert (same merchant only)."""
        ...


class MerchantProfileReader(Protocol):
    """Port for the monthly goal. Implemented by identity's SqlMerchantRepository."""

    def get(self, merchant_id: str) -> Merchant | None: ...
