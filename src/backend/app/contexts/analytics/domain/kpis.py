"""Pure, deterministic financial KPIs. No I/O: list[Transaction] in, value objects out.

Accounting rule (blueprint §6): only Accepted contributes to collected money. Declined,
Cancelled and Refunded are reported separately and never netted against collections.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, timedelta
from enum import StrEnum

from app.contexts.ledger.domain.transaction import Transaction
from app.shared.domain.date_range import DateRange
from app.shared.domain.enums import Channel, TransactionStatus
from app.shared.domain.money import Money
from app.shared.domain.rate import Rate


@dataclass(frozen=True, slots=True)
class StatusTotal:
    status: TransactionStatus
    count: int
    amount: Money


@dataclass(frozen=True, slots=True)
class KpiSnapshot:
    total_count: int
    by_status: dict[TransactionStatus, StatusTotal]
    gross_collected: Money
    accepted_count: int
    average_ticket: Money | None
    acceptance_rate: Rate  # Accepted / (Accepted + Declined)
    decline_rate: Rate  # Declined / (Accepted + Declined)
    refunded_amount: Money


def compute_kpis(transactions: Iterable[Transaction]) -> KpiSnapshot:
    counts = {s: 0 for s in TransactionStatus}
    amounts = {s: Money.zero() for s in TransactionStatus}
    for t in transactions:
        counts[t.status] += 1
        amounts[t.status] = amounts[t.status] + t.amount

    accepted = counts[TransactionStatus.ACCEPTED]
    declined = counts[TransactionStatus.DECLINED]
    gross = amounts[TransactionStatus.ACCEPTED]
    return KpiSnapshot(
        total_count=sum(counts.values()),
        by_status={s: StatusTotal(s, counts[s], amounts[s]) for s in TransactionStatus},
        gross_collected=gross,
        accepted_count=accepted,
        average_ticket=gross.average_over(accepted),
        acceptance_rate=Rate(accepted, accepted + declined),
        decline_rate=Rate(declined, accepted + declined),
        refunded_amount=amounts[TransactionStatus.REFUNDED],
    )


@dataclass(frozen=True, slots=True)
class ChannelShare:
    channel: Channel
    count: int
    count_share: Rate  # share of all transactions (count denominator)
    accepted_amount: Money
    amount_share: Rate  # share of accepted amount (centimes denominator)


def channel_mix(transactions: Iterable[Transaction]) -> list[ChannelShare]:
    txs = list(transactions)
    total_count = len(txs)
    total_accepted = sum(t.amount.centimes for t in txs if t.status.is_collected)
    result = []
    for ch in Channel:
        mine = [t for t in txs if t.channel is ch]
        accepted = Money.total(t.amount for t in mine if t.status.is_collected)
        result.append(ChannelShare(ch, len(mine), Rate(len(mine), total_count), accepted,
                                   Rate(accepted.centimes, total_accepted)))
    return result


class Granularity(StrEnum):
    DAY = "day"
    WEEK = "week"
    MONTH = "month"


def bucket_start(d: date, granularity: Granularity) -> date:
    if granularity is Granularity.WEEK:
        return d - timedelta(days=d.weekday())  # ISO week, Monday start
    if granularity is Granularity.MONTH:
        return d.replace(day=1)
    return d


def _next_bucket(d: date, granularity: Granularity) -> date:
    if granularity is Granularity.WEEK:
        return d + timedelta(days=7)
    if granularity is Granularity.MONTH:
        return (d.replace(day=28) + timedelta(days=4)).replace(day=1)
    return d + timedelta(days=1)


@dataclass(frozen=True, slots=True)
class SeriesPoint:
    bucket_start: date
    accepted_amount: Money
    accepted_count: int


def collection_series(transactions: Iterable[Transaction], period: DateRange,
                      granularity: Granularity) -> list[SeriesPoint]:
    """Accepted amount per bucket, zero-filled so gaps are visible (not interpolated)."""
    sums: dict[date, Money] = {}
    counts: dict[date, int] = {}
    for t in transactions:
        if not t.status.is_collected or not period.contains(t.occurred_at):
            continue
        b = bucket_start(t.occurred_at.date(), granularity)
        sums[b] = sums.get(b, Money.zero()) + t.amount
        counts[b] = counts.get(b, 0) + 1
    points, b = [], bucket_start(period.start, granularity)
    while b < period.end:
        points.append(SeriesPoint(b, sums.get(b, Money.zero()), counts.get(b, 0)))
        b = _next_bucket(b, granularity)
    return points
