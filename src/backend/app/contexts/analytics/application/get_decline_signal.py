from dataclasses import dataclass

from app.contexts.analytics.application.get_dashboard import TransactionReader
from app.contexts.analytics.domain.decline_signal import DeclineSignal, compute_decline_signal
from app.shared.domain.date_range import DateRange
from app.shared.domain.merchant_scope import MerchantScope


@dataclass(frozen=True, slots=True)
class DeclineInsight:
    period: DateRange
    signal: DeclineSignal


class GetDeclineSignal:
    """Read-only use case: the period's authorisation outcomes -> statistical estimate."""

    def __init__(self, reader: TransactionReader) -> None:
        self._reader = reader

    def execute(self, scope: MerchantScope, period: DateRange,
                min_attempts: int = 20) -> DeclineInsight:
        transactions = self._reader.list_in_period(scope, period)
        return DeclineInsight(
            period=period,
            signal=compute_decline_signal(transactions, min_attempts=min_attempts),
        )
