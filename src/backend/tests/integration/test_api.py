"""End-to-end through HTTP + SQL (SQLite in-memory). Covers the tenant-isolation contract."""

API = "/api/v1"


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_unauthenticated_is_rejected(client):
    assert client.get(f"{API}/transactions").status_code == 401


def test_login_error_is_generic(client):
    bad_pw = client.post(f"{API}/auth/login", json={"email": "one@test.dz", "password": "x"})
    no_user = client.post(f"{API}/auth/login", json={"email": "nobody@test.dz", "password": "x"})
    assert bad_pw.status_code == no_user.status_code == 401
    assert bad_pw.json()["detail"] == no_user.json()["detail"]


def test_me_returns_assigned_merchant(login):
    c = login()
    body = c.get(f"{API}/merchant/me").json()
    assert body["merchant"]["merchant_id"] == "M1"
    assert [a["merchant_id"] for a in body["accessible_merchants"]] == ["M1"]


def test_ledger_is_scoped_and_filters_combine(login):
    c = login()
    all_rows = c.get(f"{API}/transactions").json()
    assert all_rows["total"] == 6 and all(t["merchant_id"] == "M1" for t in all_rows["items"])

    r = c.get(f"{API}/transactions", params={"status": ["accepted", "declined"],
                                             "channel": "ecommerce", "date_from": "2026-11-18",
                                             "date_to": "2026-11-19"}).json()
    assert sorted(t["transaction_id"] for t in r["items"]) == ["T2", "T3"]


def test_cannot_read_other_merchant_transaction(login):
    c = login()
    assert c.get(f"{API}/transactions/T1").status_code == 200
    assert c.get(f"{API}/transactions/X1").status_code == 404  # exists, but not yours


def test_cannot_switch_to_unassigned_merchant(login):
    c = login()
    r = c.get(f"{API}/transactions", headers={"X-Merchant-Id": "M2"})
    assert r.status_code == 403


def test_dashboard_reconciles_with_ledger(login):
    c = login()
    params = {"date_from": "2026-11-01", "date_to": "2026-11-20"}
    d = c.get(f"{API}/analytics/dashboard", params=params).json()
    accepted = c.get(f"{API}/transactions", params={**params, "status": "accepted"}).json()
    ledger_sum = sum(t["amount"]["centimes"] for t in accepted["items"])
    assert d["kpis"]["gross_collected"]["centimes"] == ledger_sum == 350050
    assert d["kpis"]["refunded_amount"]["amount"] == "450.00"
    assert d["kpis"]["decline_rate"]["denominator"] == 3
    assert d["previous_kpis"]["gross_collected"]["amount"] == "5000.00"
    assert d["collected_change"]["kind"] == "comparable"


def test_dashboard_default_period_uses_injected_clock(login):
    d = login().get(f"{API}/analytics/dashboard").json()
    assert d["period"] == {"date_from": "2026-10-22", "date_to": "2026-11-20"}
