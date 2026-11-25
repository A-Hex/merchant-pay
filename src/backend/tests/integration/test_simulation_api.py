"""Simulator through HTTP + SQL: reconciles with the ledger, persists the run, stays scoped."""

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import ScenarioRunRow

API = "/api/v1"
BASE = {"baseline_from": "2026-11-01", "baseline_to": "2026-11-20"}


def test_plus_15_percent_projection_reconciles_with_the_ledger(login, seeded):
    c = login()
    r = c.post(f"{API}/simulations/growth", json=BASE)
    assert r.status_code == 200, r.text
    s = r.json()

    accepted = c.get(f"{API}/transactions", params={"date_from": BASE["baseline_from"],
                                                    "date_to": BASE["baseline_to"],
                                                    "status": "accepted"}).json()
    ledger_sum = sum(t["amount"]["centimes"] for t in accepted["items"])
    assert s["baseline"]["gross_collection"]["centimes"] == ledger_sum == 350050
    assert s["baseline"]["total_count"] == 5 and s["baseline"]["accepted_count"] == 2
    assert s["baseline"]["average_ticket"]["amount"] == "1750.25"

    p = s["projection"]
    assert s["assumptions"] == {"volume_growth": 0.15, "acceptance_change": 0.0, "ticket_change": 0.0}
    assert p["projected_count"] == 6  # 5 x 1.15 rounded for display
    assert p["projected_collection"]["centimes"] > ledger_sum
    assert p["delta_collection"]["centimes"] == p["projected_collection"]["centimes"] - ledger_sum
    assert p["delta_pct"] == pytest.approx(0.15, abs=0.001)

    with Session(seeded) as session:  # the run is audited
        assert session.scalar(select(func.count()).select_from(ScenarioRunRow)) == 1


def test_acceptance_change_moves_the_projection(login):
    c = login()
    base = c.post(f"{API}/simulations/growth", json=BASE).json()
    better = c.post(f"{API}/simulations/growth", json={**BASE, "acceptance_change": 0.2}).json()
    assert better["projection"]["projected_collection"]["centimes"] > \
        base["projection"]["projected_collection"]["centimes"]
    assert better["projection"]["projected_acceptance_share"] == pytest.approx(0.6)


def test_reference_period_without_accepted_rows_is_rejected(login):
    r = login().post(f"{API}/simulations/growth",
                     json={"baseline_from": "2026-11-19", "baseline_to": "2026-11-19"})
    assert r.status_code == 422  # T3/T4/T5 only: nothing accepted, so no baseline


def test_simulation_uses_only_the_callers_merchant(login):
    c = login()
    mine = c.post(f"{API}/simulations/growth", json=BASE).json()
    login("two@test.dz", "pw-two")
    theirs = c.post(f"{API}/simulations/growth", json=BASE).json()
    assert theirs["baseline"]["gross_collection"]["centimes"] == 9999900  # M2's single row only
    assert theirs["baseline"]["total_count"] == 1
    assert theirs["baseline"] != mine["baseline"]


def test_unauthenticated_is_rejected(client):
    assert client.post(f"{API}/simulations/growth", json=BASE).status_code == 401


def test_goal_gap_compares_like_for_like_periods(login):
    """FIN-001: a 15-day projection is compared with half the monthly goal, never the full month."""
    c = login()
    c.patch("/api/v1/merchant/me", json={"monthly_goal_centimes": 3_000_000})  # 30,000.00 DZD / month
    s = c.post("/api/v1/simulations/growth", json={"baseline_from": "2026-11-06", "baseline_to": "2026-11-20",
                                                  "volume_growth": 0.15}).json()
    assert s["monthly_goal"]["amount"] == "30000.00"
    assert s["goal_for_period"]["amount"] == "15000.00"  # 15 days of a 30-day month
    assert s["goal_gap"]["centimes"] == s["projection"]["projected_collection"]["centimes"] - 1_500_000
