"""Login throttling: sliding window, account vs IP counters, progressive lockout."""

import pytest

from app.shared.domain.errors import RateLimited
from app.shared.security.rate_limit import SlidingWindowLoginThrottle


class Clock:
    def __init__(self) -> None:
        self.now = 1_000.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def _throttle(clock: Clock, **kw) -> SlidingWindowLoginThrottle:
    return SlidingWindowLoginThrottle(clock=clock, **kw)


def test_blocks_after_the_limit_and_reports_retry_after():
    clock = Clock()
    t = _throttle(clock, max_attempts=3, window_seconds=60, lockout_seconds=300)
    for _ in range(3):
        t.ensure_allowed("1.2.3.4", "a@test.dz")
        t.record_failure("1.2.3.4", "a@test.dz")

    with pytest.raises(RateLimited) as err:
        t.ensure_allowed("1.2.3.4", "a@test.dz")
    assert 1 <= err.value.retry_after <= 300


def test_other_account_from_same_ip_is_still_allowed_within_ip_budget():
    clock = Clock()
    t = _throttle(clock, max_attempts=2, window_seconds=60, lockout_seconds=60, ip_limit=10)
    t.record_failure("1.2.3.4", "a@test.dz")
    t.record_failure("1.2.3.4", "a@test.dz")
    t.ensure_allowed("1.2.3.4", "b@test.dz")  # account b untouched, IP budget 2/10


def test_ip_budget_catches_spraying_many_accounts():
    clock = Clock()
    t = _throttle(clock, max_attempts=5, window_seconds=60, lockout_seconds=60, ip_limit=3)
    for i in range(3):
        t.record_failure("1.2.3.4", f"victim{i}@test.dz")
    with pytest.raises(RateLimited):
        t.ensure_allowed("1.2.3.4", "new@test.dz")


def test_success_clears_the_account_counter_but_not_an_ip_lock():
    clock = Clock()
    t = _throttle(clock, max_attempts=3, window_seconds=60, lockout_seconds=60, ip_limit=3)
    for i in range(3):
        t.record_failure("1.2.3.4", f"u{i}@test.dz")

    t.record_success("1.2.3.4", "u0@test.dz")
    with pytest.raises(RateLimited):  # IP is still locked
        t.ensure_allowed("1.2.3.4", "u0@test.dz")


def test_lockout_expires_and_backoff_grows():
    clock = Clock()
    t = _throttle(clock, max_attempts=2, window_seconds=60, lockout_seconds=100)
    t.record_failure("ip", "a@test.dz")
    t.record_failure("ip", "a@test.dz")
    with pytest.raises(RateLimited) as first:
        t.ensure_allowed("ip", "a@test.dz")
    assert first.value.retry_after == 100

    clock.advance(101)  # first lockout over; window has also expired
    t.ensure_allowed("ip", "a@test.dz")
    t.record_failure("ip", "a@test.dz")
    t.record_failure("ip", "a@test.dz")
    with pytest.raises(RateLimited) as second:
        t.ensure_allowed("ip", "a@test.dz")
    assert second.value.retry_after == 200  # exponential backoff on repeat offence


def test_window_slides_so_old_failures_do_not_count():
    clock = Clock()
    t = _throttle(clock, max_attempts=3, window_seconds=60, lockout_seconds=60, ip_limit=100)
    t.record_failure("ip", "a@test.dz")
    t.record_failure("ip", "a@test.dz")
    clock.advance(61)
    t.ensure_allowed("ip", "a@test.dz")
    t.record_failure("ip", "a@test.dz")
    t.ensure_allowed("ip", "a@test.dz")  # only 2 failures inside the window
