from datetime import date
from decimal import Decimal

import pytest

from app.contexts.alerts.domain.alert import AlertState
from app.contexts.alerts.domain.rules import CollectionDropRule, RuleContext
from app.contexts.analytics.domain.kpis import compute_kpis
from app.contexts.simulation.domain.growth import Assumptions, Baseline, simulate
from app.shared.domain.date_range import DateRange
from app.shared.domain.errors import DomainError, InvalidStateTransition
from app.shared.domain.money import Money
from tests.factories import A, D, tx

CUR = DateRange.inclusive(date(2026, 11, 7), date(2026, 11, 20))


def _ctx(current, previous):
    return RuleContext("M1", date(2026, 11, 20), CUR, CUR.previous(), current, previous)


def test_collection_drop_fires_at_20_percent_with_explanation():
    previous = [tx(f"p{i}", A, "1000", "2026-10-30 10:00") for i in range(10)]
    current = [tx(f"c{i}", A, "1000") for i in range(8)]
    alert = CollectionDropRule().evaluate(_ctx(current, previous))
    assert alert is not None and alert.delta_pct == Decimal("-0.2")
    assert "10000.00" in alert.explanation and "8000.00" in alert.explanation


def test_collection_drop_quiet_on_small_samples():
    previous = [tx(f"p{i}", A, "1000", "2026-10-30 10:00") for i in range(3)]
    assert CollectionDropRule().evaluate(_ctx([], previous)) is None


def test_alert_state_machine():
    previous = [tx(f"p{i}", A, "1000", "2026-10-30 10:00") for i in range(10)]
    alert = CollectionDropRule().evaluate(_ctx([], previous))
    alert.acknowledge()
    assert alert.state is AlertState.ACKNOWLEDGED
    with pytest.raises(InvalidStateTransition):
        alert.acknowledge()
    alert.resolve()
    with pytest.raises(InvalidStateTransition):
        alert.resolve()


def test_plus_15_percent_scales_volume_and_collection():
    baseline = Baseline(100, Decimal("0.68"), Money.of(1000))
    p = simulate(baseline, Assumptions(volume_growth=Decimal("0.15")))
    assert p.projected_count == 115
    assert p.projected_collection == Money.of(78200)
    assert p.delta_pct == Decimal("0.15")


def test_baseline_from_kpis_matches_gross_collection():
    kpis = compute_kpis([tx("1", A, "1000"), tx("2", A, "3000"), tx("3", D, "500")])
    assert Baseline.from_kpis(kpis).gross_collection == Money.of(4000)


def test_simulator_bounds():
    with pytest.raises(DomainError):
        simulate(Baseline(10, Decimal("0.9"), Money.of(10)),
                 Assumptions(Decimal("0"), acceptance_change=Decimal("0.2")))
