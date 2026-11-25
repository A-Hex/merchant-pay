"""Alerts through HTTP + SQL: idempotent evaluation, state machine, tenant isolation."""

import pytest
from sqlalchemy.orm import Session

from app.contexts.ledger.application.import_transactions import ImportTransactions
from app.contexts.ledger.infrastructure.sql_transaction_repository import (
    SqlMerchantRegistry,
    SqlTransactionRepository,
)
from app.shared.domain.enums import DataOrigin

API = "/api/v1"


def _row(tid: str, when: str) -> dict[str, object]:
    return {"transaction_id": tid, "merchant_id": "M1", "occurred_at": when, "amount": "1000.00",
            "channel": "TPE / POS", "status": "Accepted", "category": "Retail"}


def _drop_fixture(engine) -> None:
    """10 x 1,000 DZD accepted in the previous window, 4 in the current one -> a 50% drop."""
    rows = [_row(f"P{i}", f"2026-10-{25 + i % 3:02d} 10:00:00") for i in range(10)]
    rows += [_row(f"C{i}", f"2026-11-{10 + i % 2:02d} 10:00:00") for i in range(4)]
    with Session(engine) as s, s.begin():
        report = ImportTransactions(SqlTransactionRepository(s), SqlMerchantRegistry(s)).execute(
            enumerate(rows, start=500), source_name="alert-fixture",
            data_origin=DataOrigin.CHALLENGE_SOURCE)
        assert report.ok, report.errors


def test_evaluate_is_idempotent_and_explains_the_drop(client, login, seeded):
    _drop_fixture(seeded)
    c = login()
    first = c.post(f"{API}/alerts/evaluate")
    assert first.status_code == 200, first.text
    created = first.json()["created"]
    drop = next(a for a in created if a["rule_code"] == "COLLECTION_DROP")
    assert drop["severity"] == "critical"
    assert drop["unit"] == "amount"
    assert drop["window"] == {"date_from": "2026-11-07", "date_to": "2026-11-20"}
    # includes the fixture's own T6 accepted row on 2026-10-25 and T1/T2 in the current window
    assert float(drop["baseline_value"]) == pytest.approx(15000)
    assert float(drop["observed_value"]) == pytest.approx(7500.5)
    assert "DZD" in drop["explanation"] and "Seuil" in drop["explanation"]
    assert "date_from=2026-11-07" in drop["evidence_ref"]

    assert c.post(f"{API}/alerts/evaluate").json()["created"] == []  # same window -> dedupe_key


def test_alert_transitions_and_state_counts(client, login, seeded):
    _drop_fixture(seeded)
    c = login()
    created = c.post(f"{API}/alerts/evaluate").json()["created"]
    alert_id = next(a["id"] for a in created if a["rule_code"] == "COLLECTION_DROP")

    opened = c.get(f"{API}/alerts", params={"state": "open"}).json()
    assert opened["counts"]["open"] == len(created)
    assert all(a["state"] == "open" for a in opened["items"])

    ack = c.post(f"{API}/alerts/{alert_id}/acknowledge")
    assert ack.status_code == 200 and ack.json()["state"] == "acknowledged"
    assert c.post(f"{API}/alerts/{alert_id}/acknowledge").status_code == 409
    resolved = c.post(f"{API}/alerts/{alert_id}/resolve")
    assert resolved.status_code == 200 and resolved.json()["state"] == "resolved"

    counts = c.get(f"{API}/alerts").json()["counts"]
    assert counts["acknowledged"] == 0 and counts["resolved"] == 1
    assert counts["open"] == len(created) - 1


def test_alerts_are_tenant_scoped(client, login, seeded):
    _drop_fixture(seeded)
    c = login()
    alert_id = c.post(f"{API}/alerts/evaluate").json()["created"][0]["id"]

    login("two@test.dz", "pw-two")
    assert c.get(f"{API}/alerts").json()["items"] == []
    assert c.get(f"{API}/alerts").json()["counts"]["open"] == 0
    assert c.post(f"{API}/alerts/{alert_id}/acknowledge").status_code == 404
    assert c.post(f"{API}/alerts/9999/resolve").status_code == 404


def test_unauthenticated_cannot_read_alerts(client):
    assert client.get(f"{API}/alerts").status_code == 401
