"""HTTP-level security & correctness contracts: throttling, CSRF/origin, headers, RBAC,
strict validation, tenant scoping of the new insight, audit trail, readiness."""

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.container import get_login_throttle
from app.db.models import AuditEventRow
from app.shared.security.rate_limit import SlidingWindowLoginThrottle

API = "/api/v1"
LOGIN = f"{API}/auth/login"
BAD = {"email": "one@test.dz", "password": "wrong"}
GOOD = {"email": "one@test.dz", "password": "pw-one"}


# ---- login throttling -------------------------------------------------------
def test_login_is_rate_limited_with_retry_after(client):
    throttle = SlidingWindowLoginThrottle(max_attempts=2, window_seconds=60,
                                          lockout_seconds=120, ip_limit=100)
    client.app.dependency_overrides[get_login_throttle] = lambda: throttle

    for _ in range(2):
        assert client.post(LOGIN, json=BAD).status_code == 401

    blocked = client.post(LOGIN, json=BAD)
    assert blocked.status_code == 429
    assert blocked.json()["code"] == "RateLimited"
    assert blocked.headers["retry-after"] == "120"

    # The lock is enforced before credential verification, so even the right password waits.
    assert client.post(LOGIN, json=GOOD).status_code == 429


def test_rate_limited_response_has_no_enumerating_detail(client):
    throttle = SlidingWindowLoginThrottle(max_attempts=1, window_seconds=60, lockout_seconds=60)
    client.app.dependency_overrides[get_login_throttle] = lambda: throttle
    client.post(LOGIN, json=BAD)
    body = client.post(LOGIN, json=BAD).json()
    assert body["detail"] == "Too many attempts; try again later"


# ---- response hardening -----------------------------------------------------
def test_security_headers_and_request_id_are_present(client):
    r = client.get("/health", headers={"X-Request-ID": "trace-123"})
    assert r.headers["x-request-id"] == "trace-123"
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["x-frame-options"] == "DENY"
    assert r.headers["cache-control"] == "no-store"
    assert "default-src 'none'" in r.headers["content-security-policy"]


def test_cross_origin_unsafe_request_is_rejected(client):
    r = client.post(LOGIN, json=GOOD, headers={"Origin": "https://evil.example"})
    assert r.status_code == 403
    assert r.json()["code"] == "OriginRejected"


def test_allowed_origin_is_accepted(client):
    r = client.post(LOGIN, json=GOOD, headers={"Origin": "http://localhost:5173"})
    assert r.status_code == 204


def test_readiness_checks_the_database(client):
    r = client.get("/ready")
    assert r.status_code == 200
    assert r.json() == {"status": "ready", "checks": {"database": "ok"}}


# ---- profile: strict validation + RBAC -------------------------------------
def test_profile_update_round_trip(login):
    c = login()
    r = c.patch(f"{API}/merchant/me", json={"display_name": "  Merchant One  ",
                                            "category": "Retail & Food",
                                            "operating_days": ["mon", "tue", "wed"],
                                            "monthly_goal_centimes": 1_234_500})
    assert r.status_code == 200, r.text
    updated = r.json()
    assert updated["display_name"] == "Merchant One"  # normalised, not trusted verbatim
    assert updated["operating_days"] == ["mon", "tue", "wed"]
    assert updated["monthly_goal"] == {"amount": "12345.00", "centimes": 1_234_500,
                                       "currency": "DZD"}

    me = c.get(f"{API}/merchant/me").json()["merchant"]
    assert me["display_name"] == "Merchant One" and me["category"] == "Retail & Food"


@pytest.mark.parametrize("payload", [
    {"unknown_field": 1},            # extra="forbid"
    {},                              # nothing to update
    {"display_name": "   "},         # blank after trim
    {"operating_days": []},          # at least one day
    {"operating_days": ["mon", "mon"]},  # duplicates
    {"operating_days": ["monday"]},  # unknown token
    {"monthly_goal_centimes": -1},   # negative money
    {"monthly_goal_centimes": "abc"},
])
def test_profile_rejects_invalid_payloads(login, payload):
    r = login().patch(f"{API}/merchant/me", json=payload)
    assert r.status_code == 422, r.text


def test_profile_can_clear_the_monthly_goal(login):
    c = login()
    c.patch(f"{API}/merchant/me", json={"monthly_goal_centimes": 5_000_000})
    cleared = c.patch(f"{API}/merchant/me", json={"monthly_goal_centimes": None})
    assert cleared.status_code == 200
    assert cleared.json()["monthly_goal"] is None


def test_staff_can_read_but_not_edit_the_profile(client, login):
    login("staff@test.dz", "pw-staff")
    assert client.get(f"{API}/merchant/me").status_code == 200
    r = client.patch(f"{API}/merchant/me", json={"display_name": "Staff Edit"})
    assert r.status_code == 403
    assert r.json()["code"] == "Forbidden"


def test_profile_requires_authentication(client):
    assert client.patch(f"{API}/merchant/me", json={"display_name": "x"}).status_code == 401


# ---- insights ---------------------------------------------------------------
def test_decline_insight_is_scoped_and_statistically_sound(login):
    s = login().get(f"{API}/insights/decline",
                    params={"date_from": "2026-11-01", "date_to": "2026-11-20"}).json()["signal"]
    assert (s["accepted"], s["declined"], s["attempts"]) == (2, 1, 3)
    assert s["observed_rate"]["value"] == pytest.approx(1 / 3)
    assert s["posterior_mean"] == pytest.approx((1 + 0.5) / (3 + 1), abs=1e-6)
    assert 0 <= s["credible_interval"]["lower"] < s["posterior_mean"] < s["credible_interval"]["upper"] <= 1
    assert s["credible_interval"]["level"] == pytest.approx(0.9)
    assert s["sample_gate_met"] is False  # 3 attempts < 20
    assert s["prior"]["family"].startswith("Jeffreys")
    assert "not proof of fraud" in s["limitations"]


def test_decline_insight_never_leaks_another_tenant(login):
    s = login("two@test.dz", "pw-two").get(f"{API}/insights/decline",
                                           params={"date_from": "2026-11-01",
                                                   "date_to": "2026-11-20"}).json()["signal"]
    assert (s["accepted"], s["declined"], s["attempts"]) == (1, 0, 1)  # X1 only, no M1 rows


def test_decline_insight_changes_with_the_sample_gate(login):
    c = login()
    strict = c.get(f"{API}/insights/decline", params={"min_attempts": 20}).json()["signal"]
    relaxed = c.get(f"{API}/insights/decline", params={"min_attempts": 1}).json()["signal"]
    assert strict["sample_gate_met"] is False and relaxed["sample_gate_met"] is True


def test_decline_insight_rejects_an_invalid_period(login):
    r = login().get(f"{API}/insights/decline",
                    params={"date_from": "2026-11-20", "date_to": "2026-11-01"})
    assert r.status_code == 422


def test_ledger_search_escapes_like_wildcards(login):
    c = login()
    assert c.get(f"{API}/transactions", params={"q": "%"}).json()["total"] == 0
    assert c.get(f"{API}/transactions", params={"q": "T1"}).json()["total"] >= 1


# ---- audit trail ------------------------------------------------------------
def test_login_profile_and_simulation_are_audited(client, seeded, login):
    c = login()
    c.patch(f"{API}/merchant/me", json={"display_name": "Audited Merchant"})
    assert c.post(f"{API}/simulations/growth", json={}).status_code == 200

    with Session(seeded) as s:
        actions = {row.action for row in s.scalars(select(AuditEventRow))}
    assert {"auth.login_succeeded", "merchant.profile_updated",
            "simulation.growth_run"} <= actions
