from datetime import date
from decimal import Decimal

import pytest

from app.shared.domain.date_range import DateRange
from app.shared.domain.enums import Channel, TransactionStatus
from app.shared.domain.errors import DomainError
from app.shared.domain.money import Money
from app.shared.domain.rate import Rate


def test_money_is_exact_in_centimes():
    assert Money.of("0.1") + Money.of("0.2") == Money.of("0.3")
    assert Money.of("1435187.14").centimes == 143518714
    assert Money.of("10.005").centimes == 1001  # half-up


def test_money_average_never_divides_by_zero():
    assert Money.of(100).average_over(0) is None
    assert Money.of(100).average_over(3) == Money.of("33.33")


def test_date_range_half_open_and_previous():
    r = DateRange.inclusive(date(2026, 11, 1), date(2026, 11, 30))
    assert r.days == 30 and r.contains(date(2026, 11, 30)) and not r.contains(date(2026, 12, 1))
    assert r.previous() == DateRange(date(2026, 10, 2), date(2026, 11, 1))


def test_date_range_rejects_empty():
    with pytest.raises(DomainError):
        DateRange(date(2026, 1, 2), date(2026, 1, 2))


def test_rate_undefined_when_denominator_zero():
    assert Rate(0, 0).value is None
    assert Rate(1, 4).value == Decimal("0.25")


@pytest.mark.parametrize("raw,expected", [
    ("Accepted", TransactionStatus.ACCEPTED), ("Accepté", TransactionStatus.ACCEPTED),
    ("REFUNDED", TransactionStatus.REFUNDED), ("Annulé", TransactionStatus.CANCELLED),
])
def test_status_parsing(raw, expected):
    assert TransactionStatus.parse(raw) is expected


def test_channel_parsing():
    assert Channel.parse("Contactless / NFC") is Channel.CONTACTLESS
    assert Channel.parse("TPE / POS") is Channel.POS
    with pytest.raises(ValueError):
        Channel.parse("Cash")
