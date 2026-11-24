"""Collections through HTTP + SQL: every status reconciles with the ledger, B deltas are safe at zero."""

import pytest

API = "/api/v1"
PERIOD_A = {"a_from": "2026-11-01", "a_to": "2026-11-20"}
PERIOD_B = {"b_from": "2026-10-01", "b_to": "2026-10-31"}


def test_status_totals_reconcile_with_the_ledger(login):
    c = login()
    s = c.get(f"{API}/collections/summary", params={**PERIOD_A, **PERIOD_B}).json()
    rows = {row["status"]: row for row in s["by_status"]}
    for status in ("accepted", "declined", "cancelled", "refunded"):
        ledger = c.get(f"{API}/transactions", params={"date_from": PERIOD_A["a_from"],
                                                        "date_to": PERIOD_A["a_to"],
                                                        "status": status}).json()
        assert rows[status]["count_a"] == ledger["total"]
        assert rows[status]["amount_a"]["centimes"] == sum(
            t["amount"]["centimes"] for t in ledger["items"])

    # accepted is the only collected amount; the others stay separate
    assert s["collected_a"]["centimes"] == rows["accepted"]["amount_a"]["centimes"] == 350050
    assert rows["declined"]["amount_a"]["amount"] == "700.00"
    assert rows["cancelled"]["amount_a"]["amount"] == "300.00"
    assert rows["refunded"]["amount_a"]["amount"] == "450.00"
    assert s["total_count_a"] == 5


def test_deltas_compare_a_against_b(login):
    s = login().get(f"{API}/collections/summary", params={**PERIOD_A, **PERIOD_B}).json()
    assert s["collected_b"]["amount"] == "5000.00"
    assert s["collected_change"]["kind"] == "comparable"
    assert s["collected_change"]["pct"] == pytest.approx((350050 - 500000) / 500000)
    assert s["collected_change"]["delta"] == 350050 - 500000


def test_zero_reference_period_is_new_activity_not_infinity(login):
    s = login().get(f"{API}/collections/summary",
                    params={**PERIOD_A, "b_from": "2026-09-01", "b_to": "2026-09-30"}).json()
    assert s["collected_b"]["centimes"] == 0
    assert s["collected_change"]["kind"] == "new_activity"
    assert s["collected_change"]["pct"] is None
    assert s["acceptance_rate_b"]["value"] is None


def test_period_b_defaults_to_the_period_before_a(login):
    s = login().get(f"{API}/collections/summary", params=PERIOD_A).json()
    assert s["period_b"] == {"date_from": "2026-10-12", "date_to": "2026-10-31"}


def test_collections_are_tenant_scoped(login):
    c = login()
    login("two@test.dz", "pw-two")
    s = c.get(f"{API}/collections/summary", params=PERIOD_A).json()
    assert s["collected_a"]["centimes"] == 9999900  # M2's single accepted row
    assert s["total_count_a"] == 1
    assert next(r for r in s["by_status"] if r["status"] == "accepted")["count_a"] == 1


def test_unauthenticated_is_rejected(client):
    assert client.get(f"{API}/collections/summary", params=PERIOD_A).status_code == 401
