"""Login throttling (429 + Retry-After) and login audit events."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AuditEventRow

LOGIN = "/api/v1/auth/login"


def test_sixth_failure_is_throttled_even_with_the_right_password(client):
    for _ in range(5):
        assert client.post(LOGIN, json={"email": "one@test.dz", "password": "bad"}).status_code == 401
    r = client.post(LOGIN, json={"email": "one@test.dz", "password": "pw-one"})
    assert r.status_code == 429
    assert 0 < int(r.headers["Retry-After"]) <= 900
    assert r.json()["code"] == "TooManyAttempts"
    # another account from the same IP is still allowed (IP limit is higher)
    assert client.post(LOGIN, json={"email": "two@test.dz", "password": "pw-two"}).status_code == 204


def test_successful_login_resets_counter_and_is_audited(client, seeded):
    for _ in range(4):
        client.post(LOGIN, json={"email": "one@test.dz", "password": "bad"})
    assert client.post(LOGIN, json={"email": "one@test.dz", "password": "pw-one"}).status_code == 204
    for _ in range(4):  # counter was reset: 4 more failures still do not throttle
        assert client.post(LOGIN, json={"email": "one@test.dz", "password": "bad"}).status_code == 401
    with Session(seeded) as s:
        events = s.scalars(select(AuditEventRow).where(AuditEventRow.action == "auth.login")).all()
        assert len(events) == 1 and events[0].actor_id is not None


def test_security_headers_on_api_responses(client):
    r = client.get("/api/v1/merchant/me")
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["x-frame-options"] == "DENY"
    assert r.headers["content-security-policy"] == "default-src 'none'; frame-ancestors 'none'"
    assert "content-security-policy" not in client.get("/api/docs").headers  # Swagger UI needs its assets


def test_state_changing_requests_from_foreign_origins_are_refused(client):
    body = {"email": "one@test.dz", "password": "pw-one"}
    evil = client.post(LOGIN, json=body, headers={"Origin": "https://evil.example"})
    assert evil.status_code == 403 and evil.json()["code"] == "OriginRefused"
    assert client.post(LOGIN, json=body, headers={"Origin": "null"}).status_code == 403
    assert client.post(LOGIN, json=body, headers={"Origin": "http://localhost:5173"}).status_code == 204
    same_host = {"Origin": "http://testserver"}
    assert client.post(LOGIN, json=body, headers=same_host).status_code == 204
    assert client.post(LOGIN, json=body).status_code == 204  # non-browser client: no Origin header
    # reads are never blocked by the guard (CORS still governs what a browser may read)
    assert client.get("/api/v1/merchant/me", headers={"Origin": "https://evil.example"}).status_code == 200


def test_dev_proxy_forwarded_host_counts_as_same_site(client):
    """The Vite proxy rewrites Host to the API; X-Forwarded-Host carries the address the user opened."""
    body = {"email": "one@test.dz", "password": "pw-one"}
    via_proxy = {"Origin": "http://127.0.0.1:5173", "X-Forwarded-Host": "127.0.0.1:5173"}
    assert client.post(LOGIN, json=body, headers=via_proxy).status_code == 204
    spoof = {"Origin": "https://evil.example", "X-Forwarded-Host": "127.0.0.1:5173"}
    assert client.post(LOGIN, json=body, headers=spoof).status_code == 403  # header must match the Origin
