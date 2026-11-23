"""Period-over-period change that never divides by zero (blueprint §6 'Period change')."""

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum


class ChangeKind(StrEnum):
    COMPARABLE = "comparable"
    NEW_ACTIVITY = "new_activity"  # previous == 0, current > 0
    NO_ACTIVITY = "no_activity"  # both zero


@dataclass(frozen=True, slots=True)
class PeriodChange:
    current: int
    previous: int
    delta: int
    pct: Decimal | None  # None unless kind == COMPARABLE
    kind: ChangeKind


def compare(current: int, previous: int) -> PeriodChange:
    """Works on ints: counts, or Money.centimes."""
    delta = current - previous
    if previous == 0:
        kind = ChangeKind.NO_ACTIVITY if current == 0 else ChangeKind.NEW_ACTIVITY
        return PeriodChange(current, previous, delta, None, kind)
    return PeriodChange(current, previous, delta, Decimal(delta) / Decimal(previous),
                        ChangeKind.COMPARABLE)
