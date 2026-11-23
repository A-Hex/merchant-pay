"""Half-open calendar period [start, end). The ONLY place period arithmetic lives."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta

from app.shared.domain.errors import DomainError


@dataclass(frozen=True, slots=True)
class DateRange:
    start: date
    end: date  # exclusive

    def __post_init__(self) -> None:
        if self.end <= self.start:
            raise DomainError(f"Invalid period: end {self.end} must be after start {self.start}")

    @classmethod
    def inclusive(cls, first_day: date, last_day: date) -> DateRange:
        """Build from the inclusive dates a user picks in the UI."""
        return cls(first_day, last_day + timedelta(days=1))

    @classmethod
    def last_n_days(cls, today: date, n: int) -> DateRange:
        end = today + timedelta(days=1)
        return cls(end - timedelta(days=n), end)

    @property
    def days(self) -> int:
        return (self.end - self.start).days

    @property
    def last_day(self) -> date:
        return self.end - timedelta(days=1)

    def contains(self, moment: date | datetime) -> bool:
        d = moment.date() if isinstance(moment, datetime) else moment
        return self.start <= d < self.end

    def previous(self) -> DateRange:
        """Like-for-like prior period of the same length, immediately before this one."""
        return DateRange(self.start - timedelta(days=self.days), self.start)

    def start_datetime(self) -> datetime:
        return datetime.combine(self.start, datetime.min.time())

    def end_datetime(self) -> datetime:
        return datetime.combine(self.end, datetime.min.time())
