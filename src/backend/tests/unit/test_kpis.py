from datetime import date
from decimal import Decimal

from app.contexts.analytics.domain.kpis import Granularity, collection_series, compute_kpis
from app.contexts.analytics.domain.period_comparison import ChangeKind, compare
from app.shared.domain.date_range import DateRange
from app.shared.domain.money import Money
from tests.factories import A, C, D, R, tx

TXS = [tx("1", A, "1000"), tx("2", A, "2500.50"), tx("3", D, "700"), tx("4", C, "300"),
       tx("5", R, "450")]


def test_only_accepted_is_collected_and_statuses_stay_separate():
    k = compute_kpis(TXS)
    assert k.gross_collected == Money.of("3500.50")
    assert k.total_count == 5 and k.accepted_count == 2
    assert k.by_status[D].amount == Money.of(700)
    assert k.by_status[C].amount == Money.of(300)
    assert k.refunded_amount == Money.of(450)  # shown separately, NOT netted


def test_rates_use_authorization_denominator():
    k = compute_kpis(TXS)
    assert (k.acceptance_rate.numerator, k.acceptance_rate.denominator) == (2, 3)
    assert (k.decline_rate.numerator, k.decline_rate.denominator) == (1, 3)
    assert k.average_ticket == Money.of("1750.25")


def test_empty_period_is_safe():
    k = compute_kpis([])
    assert k.average_ticket is None and k.acceptance_rate.value is None


def test_series_is_zero_filled_and_accepted_only():
    period = DateRange.inclusive(date(2026, 11, 9), date(2026, 11, 11))
    pts = collection_series(TXS, period, Granularity.DAY)
    assert [p.bucket_start.day for p in pts] == [9, 10, 11]
    assert pts[1].accepted_amount == Money.of("3500.50") and pts[0].accepted_count == 0


def test_period_change_handles_zero_previous():
    assert compare(100, 0).kind is ChangeKind.NEW_ACTIVITY
    assert compare(0, 0).kind is ChangeKind.NO_ACTIVITY
    c = compare(80, 100)
    assert c.kind is ChangeKind.COMPARABLE and c.pct == Decimal("-0.2")
