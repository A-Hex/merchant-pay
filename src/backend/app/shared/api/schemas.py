"""Reusable response shapes. Money is sent as exact decimal string + centimes (never float)."""

from datetime import date, timedelta

from pydantic import BaseModel

from app.shared.domain.date_range import DateRange
from app.shared.domain.money import Money
from app.shared.domain.rate import Rate


class MoneyOut(BaseModel):
    amount: str  # "1435187.14"
    centimes: int
    currency: str = "DZD"

    @classmethod
    def of(cls, m: Money) -> "MoneyOut":
        return cls(amount=str(m.to_decimal()), centimes=m.centimes, currency=m.currency)


class RateOut(BaseModel):
    numerator: int
    denominator: int
    value: float | None  # display only; None when denominator is 0

    @classmethod
    def of(cls, r: Rate) -> "RateOut":
        v = r.value
        return cls(numerator=r.numerator, denominator=r.denominator,
                   value=float(v) if v is not None else None)


class PeriodOut(BaseModel):
    date_from: date
    date_to: date  # inclusive, as the user sees it

    @classmethod
    def of(cls, p: DateRange) -> "PeriodOut":
        return cls(date_from=p.start, date_to=p.last_day)


def period_from_query(date_from: date | None, date_to: date | None, today: date,
                      default_days: int = 30) -> DateRange:
    """UI sends inclusive dates; domain uses half-open ranges."""
    if date_from is None and date_to is None:
        return DateRange.last_n_days(today, default_days)
    end = date_to or today
    start = date_from or end - timedelta(days=default_days - 1)
    return DateRange.inclusive(start, end)
