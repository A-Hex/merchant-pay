"""Money value object: DZD amounts stored as integer centimes. Never use float for money."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from app.shared.domain.errors import DomainError

_CENTS = Decimal(100)


@dataclass(frozen=True, slots=True, order=True)
class Money:
    centimes: int
    currency: str = "DZD"

    @classmethod
    def zero(cls) -> Money:
        return cls(0)

    @classmethod
    def of(cls, value: Decimal | str | int | float) -> Money:
        """Build from a unit amount, e.g. Money.of("1250.50") -> 125050 centimes."""
        d = Decimal(str(value))
        return cls(int((d * _CENTS).quantize(Decimal(1), rounding=ROUND_HALF_UP)))

    @classmethod
    def total(cls, items: Iterable[Money]) -> Money:
        result = cls.zero()
        for m in items:
            result = result + m
        return result

    def to_decimal(self) -> Decimal:
        return (Decimal(self.centimes) / _CENTS).quantize(Decimal("0.01"))

    def scale(self, factor: Decimal) -> Money:
        scaled = (Decimal(self.centimes) * factor).quantize(Decimal(1), rounding=ROUND_HALF_UP)
        return Money(int(scaled), self.currency)

    def average_over(self, parts: int) -> Money | None:
        """Average per part (e.g. average ticket). None when parts == 0, never divide by zero."""
        if parts <= 0:
            return None
        return self.scale(Decimal(1) / Decimal(parts))

    def _check(self, other: Money) -> None:
        if self.currency != other.currency:
            raise DomainError(f"Currency mismatch: {self.currency} vs {other.currency}")

    def __add__(self, other: Money) -> Money:
        self._check(other)
        return Money(self.centimes + other.centimes, self.currency)

    def __sub__(self, other: Money) -> Money:
        self._check(other)
        return Money(self.centimes - other.centimes, self.currency)

    def __str__(self) -> str:
        return f"{self.to_decimal():,} {self.currency}"
