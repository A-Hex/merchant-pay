"""Status-separated totals for two periods (module 03). Statuses are never netted together."""

from dataclasses import dataclass

from app.contexts.analytics.application.get_dashboard import TransactionReader
from app.contexts.analytics.domain.kpis import KpiSnapshot, StatusTotal, compute_kpis
from app.contexts.analytics.domain.period_comparison import PeriodChange, compare
from app.shared.domain.date_range import DateRange
from app.shared.domain.enums import TransactionStatus
from app.shared.domain.merchant_scope import MerchantScope


@dataclass(frozen=True, slots=True)
class StatusComparison:
    status: TransactionStatus
    a: StatusTotal
    b: StatusTotal
    count_change: PeriodChange
    amount_change: PeriodChange


@dataclass(frozen=True, slots=True)
class CollectionsSummary:
    period_a: DateRange
    period_b: DateRange
    totals_a: KpiSnapshot
    totals_b: KpiSnapshot
    by_status: list[StatusComparison]
    collected_change: PeriodChange
    total_count_change: PeriodChange


class GetCollectionsSummary:
    def __init__(self, reader: TransactionReader) -> None:
        self._reader = reader

    def execute(self, scope: MerchantScope, period_a: DateRange,
                period_b: DateRange) -> CollectionsSummary:
        a = compute_kpis(self._reader.list_in_period(scope, period_a))
        b = compute_kpis(self._reader.list_in_period(scope, period_b))
        return CollectionsSummary(
            period_a=period_a,
            period_b=period_b,
            totals_a=a,
            totals_b=b,
            by_status=[
                StatusComparison(
                    status=status,
                    a=a.by_status[status],
                    b=b.by_status[status],
                    count_change=compare(a.by_status[status].count, b.by_status[status].count),
                    amount_change=compare(a.by_status[status].amount.centimes,
                                          b.by_status[status].amount.centimes),
                )
                for status in TransactionStatus
            ],
            collected_change=compare(a.gross_collected.centimes, b.gross_collected.centimes),
            total_count_change=compare(a.total_count, b.total_count),
        )
