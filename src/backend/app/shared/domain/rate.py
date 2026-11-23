"""Rate value object: keeps numerator and denominator together (never a bare percentage)."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class Rate:
    numerator: int
    denominator: int

    @property
    def value(self) -> Decimal | None:
        """None when the denominator is zero: the rate is undefined, not 0%."""
        if self.denominator == 0:
            return None
        return Decimal(self.numerator) / Decimal(self.denominator)
