"""Collections Summary report: an AGGREGATED, shareable view of one merchant's period.

Built only from the analytics domain functions that power the screens (compute_kpis, channel_mix,
compare), so a report can never disagree with the dashboard or the collections page. It contains no
transaction rows, no customer identifiers and no card data. Provenance (synthetic vs challenge source)
travels with the report so a synthetic report can never pass for a bank or SATIM statement.
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime

from app.contexts.analytics.domain.kpis import ChannelShare, KpiSnapshot, channel_mix, compute_kpis
from app.contexts.analytics.domain.period_comparison import PeriodChange, compare
from app.contexts.ledger.domain.transaction import Transaction
from app.shared.domain.date_range import DateRange
from app.shared.domain.enums import DataOrigin
from app.shared.domain.errors import DomainError

MAX_REPORT_DAYS = 366


@dataclass(frozen=True, slots=True)
class CollectionsReport:
    merchant_id: str
    merchant_name: str
    period: DateRange
    previous_period: DateRange
    generated_at: datetime
    kpis: KpiSnapshot
    previous_kpis: KpiSnapshot
    collected_change: PeriodChange
    channels: list[ChannelShare]
    provenance: dict[DataOrigin, int]  # transactions per data origin in the period

    @property
    def synthetic(self) -> bool:
        return self.provenance.get(DataOrigin.SYNTHETIC_DEMO, 0) > 0


def validate_period(period: DateRange) -> None:
    if period.days > MAX_REPORT_DAYS:
        raise DomainError(f"A report covers at most {MAX_REPORT_DAYS} days")


def build_report(
    merchant_id: str,
    merchant_name: str,
    period: DateRange,
    current: Iterable[Transaction],
    previous: Iterable[Transaction],
    generated_at: datetime,
) -> CollectionsReport:
    validate_period(period)
    cur, prev = list(current), list(previous)
    k, p = compute_kpis(cur), compute_kpis(prev)
    return CollectionsReport(
        merchant_id=merchant_id,
        merchant_name=merchant_name,
        period=period,
        previous_period=period.previous(),
        generated_at=generated_at,
        kpis=k,
        previous_kpis=p,
        collected_change=compare(k.gross_collected.centimes, p.gross_collected.centimes),
        channels=channel_mix(cur),
        provenance=dict(Counter(t.data_origin for t in cur)),
    )


_UNSAFE = re.compile(r"[^A-Za-z0-9._-]+")


def safe_filename(merchant_id: str, period: DateRange, extension: str) -> str:
    """ASCII-only, no path separators, no quotes: safe in a Content-Disposition header and on disk."""
    stem = f"ceo-pay_collections_{merchant_id}_{period.start}_{period.last_day}"
    return _UNSAFE.sub("-", stem)[:120] + "." + extension
