from datetime import UTC, datetime, timedelta

from app.contexts.identity.application.use_cases import GetLoginHistory
from app.contexts.identity.domain.model import LoginEvent, LoginOutcome, device_label

NOW = datetime(2026, 11, 25, 12, tzinfo=UTC)
S, F, T, L = LoginOutcome.SUCCESS, LoginOutcome.FAILURE, LoginOutcome.THROTTLED, LoginOutcome.LOGOUT


def test_device_label_keeps_only_browser_family_and_os():
    chrome_linux = (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36"
    )
    assert device_label(chrome_linux) == "Chrome · Linux"
    assert (
        device_label("Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) Version/18.0 Safari/605.1")
        == "Safari · iOS"
    )
    assert (
        device_label("Mozilla/5.0 (Windows NT 10.0) Chrome/131.0 Safari/537.36 Edg/131.0") == "Edge · Windows"
    )
    assert device_label("curl/8.0") == "unknown" and device_label("") == "unknown"


class FakeHistory:
    def __init__(self, events):
        self.events = sorted(events, key=lambda e: e.occurred_at, reverse=True)

    def recent(self, user_id, limit):
        return self.events[:limit]


def ev(outcome, days_ago):
    return LoginEvent(1, outcome, NOW - timedelta(days=days_ago), "10.0.0.1", "ua")


def test_summary_counts_recent_failures_and_finds_the_previous_login():
    h = GetLoginHistory(FakeHistory([ev(S, 0), ev(F, 1), ev(T, 2), ev(L, 3), ev(S, 5), ev(F, 40), ev(S, 50)]))
    r = h.execute(1, NOW, limit=3)
    assert [e.outcome for e in r.events] == [S, F, T]  # newest first, limited
    assert r.failures_last_30_days == 2  # the 40-day-old failure is outside the window
    assert r.previous_success == NOW - timedelta(days=5)  # not the current session's login
    assert GetLoginHistory(FakeHistory([ev(S, 0)])).execute(1, NOW).previous_success is None
