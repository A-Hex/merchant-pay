"""Login history over HTTP: failures survive the rollback, unknown e-mails are not stored, scoped per user."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import LoginEventRow, UserRow

LOGIN, HISTORY = "/api/v1/auth/login", "/api/v1/auth/history"
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) Chrome/131.0 Safari/537.36"}


def _outcomes(c):
    return [e["outcome"] for e in c.get(HISTORY).json()["events"]]


def test_failures_successes_and_logouts_are_recorded_newest_first(client, seeded):
    assert client.post(LOGIN, json={"email": "one@test.dz", "password": "bad"}, headers=UA).status_code == 401
    assert client.post(LOGIN, json={"email": "nobody@test.dz", "password": "x"}).status_code == 401
    assert (
        client.post(LOGIN, json={"email": "one@test.dz", "password": "pw-one"}, headers=UA).status_code == 204
    )
    h = client.get(HISTORY).json()
    assert [e["outcome"] for e in h["events"]] == [
        "success",
        "failure",
    ]  # the 401's event was not rolled back
    assert h["events"][0]["device"] == "Chrome · Linux" and h["failures_last_30_days"] == 1
    assert h["previous_success"] is None and h["retention_days"] == 90
    with Session(seeded) as s:  # the unknown address left no trace
        assert s.scalar(select(LoginEventRow).where(LoginEventRow.user_id.is_(None))) is None
        assert len(s.scalars(select(LoginEventRow)).all()) == 2
    client.post("/api/v1/auth/logout")
    client.post(LOGIN, json={"email": "one@test.dz", "password": "pw-one"})
    h2 = client.get(HISTORY).json()
    assert [e["outcome"] for e in h2["events"]][:3] == ["success", "logout", "success"]
    assert h2["previous_success"] is not None


def test_throttled_attempts_are_recorded(client, seeded):
    for _ in range(5):
        client.post(LOGIN, json={"email": "one@test.dz", "password": "bad"})
    assert client.post(LOGIN, json={"email": "one@test.dz", "password": "pw-one"}).status_code == 429
    with Session(seeded) as s:
        uid = s.scalar(select(UserRow.id).where(UserRow.email == "one@test.dz"))
        outcomes = [r.outcome for r in s.scalars(select(LoginEventRow).where(LoginEventRow.user_id == uid))]
    assert outcomes.count("failure") == 5 and outcomes.count("throttled") == 1 and "success" not in outcomes


def test_history_is_per_user_and_requires_auth(client, login):
    assert client.get(HISTORY).status_code == 401
    one = login()
    one.post(LOGIN, json={"email": "one@test.dz", "password": "bad"})  # a failure on ONE's account
    two = login("two@test.dz", "pw-two")
    assert _outcomes(two) == ["success"]  # two never sees one's events
    assert two.get(HISTORY, params={"limit": 0}).status_code == 422
    assert two.get(HISTORY, params={"limit": 101}).status_code == 422


def test_old_events_are_pruned_after_retention(client, seeded):
    with Session(seeded) as s, s.begin():
        uid = s.scalar(select(UserRow.id).where(UserRow.email == "one@test.dz"))
        s.add(
            LoginEventRow(
                user_id=uid,
                outcome="success",
                occurred_at=datetime.now(UTC) - timedelta(days=120),
                ip="1.1.1.1",
                user_agent="old",
            )
        )
    client.post(LOGIN, json={"email": "one@test.dz", "password": "pw-one"})
    with Session(seeded) as s:
        agents = [r.user_agent for r in s.scalars(select(LoginEventRow))]
    assert "old" not in agents and len(agents) == 1  # the 120-day-old event was pruned by the new write
