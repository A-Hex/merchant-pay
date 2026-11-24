"""In-process login throttling.

Two independent sliding windows are enforced on every attempt:

* per account (``email``) - the primary brute-force defence;
* per client IP - a wider net (4x the account limit by default) so one host cannot
  spray many accounts, while avoiding locking out a whole shared/NAT network after
  a handful of typos.

Repeated lockouts back off exponentially (capped at 24 h). State is in-process and
therefore per worker; a multi-instance deployment must put the same interface in
front of Redis or a DB table. That limitation is documented in ``docs/security.md``.
"""

import math
import threading
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field

from app.shared.domain.errors import RateLimited

_MAX_LOCKOUT_SECONDS = 24 * 60 * 60
_MAX_TRACKED_KEYS = 10_000


@dataclass
class _Bucket:
    failures: deque[float] = field(default_factory=deque)
    locked_until: float = 0.0
    strikes: int = 0
    last_seen: float = 0.0


class SlidingWindowLoginThrottle:
    """Thread-safe, injectable-clock limiter that satisfies the ``LoginThrottle`` port."""

    def __init__(self, max_attempts: int = 5, window_seconds: int = 300,
                 lockout_seconds: int = 900, *, ip_limit: int | None = None,
                 clock: Callable[[], float] = time.monotonic) -> None:
        if max_attempts < 1:
            raise ValueError("max_attempts must be >= 1")
        self._max = max_attempts
        self._ip_limit = max_attempts * 4 if ip_limit is None else max(1, ip_limit)
        self._window = window_seconds
        self._lockout = lockout_seconds
        self._clock = clock
        self._buckets: dict[str, _Bucket] = {}
        self._lock = threading.Lock()

    # -- public API (LoginThrottle port) --------------------------------------
    def ensure_allowed(self, client_ip: str, email: str) -> None:
        now = self._clock()
        with self._lock:
            wait = max(self._remaining(self._get(f"ip:{client_ip}", now), now),
                       self._remaining(self._get(f"email:{email}", now), now))
        if wait > 0:
            raise RateLimited(math.ceil(wait))

    def record_failure(self, client_ip: str, email: str) -> None:
        now = self._clock()
        with self._lock:
            self._push(f"ip:{client_ip}", now, self._ip_limit)
            self._push(f"email:{email}", now, self._max)

    def record_success(self, client_ip: str, email: str) -> None:
        # Clear the account counter only. A valid login must not reset an IP-level
        # lock, otherwise an attacker with one known account could bypass IP limits.
        with self._lock:
            self._buckets.pop(f"email:{email}", None)

    def reset(self) -> None:
        with self._lock:
            self._buckets.clear()

    # -- internals -----------------------------------------------------------
    def _get(self, key: str, now: float) -> _Bucket:
        bucket = self._buckets.get(key)
        if bucket is None:
            bucket = self._buckets[key] = _Bucket(last_seen=now)
            self._evict_if_needed()
        bucket.last_seen = now
        return bucket

    def _remaining(self, bucket: _Bucket, now: float) -> float:
        return max(0.0, bucket.locked_until - now)

    def _push(self, key: str, now: float, limit: int) -> None:
        bucket = self._get(key, now)
        bucket.failures.append(now)
        self._prune(bucket, now)
        if len(bucket.failures) >= limit:
            bucket.strikes += 1
            duration = min(self._lockout * (2 ** (bucket.strikes - 1)), _MAX_LOCKOUT_SECONDS)
            bucket.locked_until = now + duration
            bucket.failures.clear()

    def _prune(self, bucket: _Bucket, now: float) -> None:
        cutoff = now - self._window
        while bucket.failures and bucket.failures[0] < cutoff:
            bucket.failures.popleft()

    def _evict_if_needed(self) -> None:
        if len(self._buckets) <= _MAX_TRACKED_KEYS:
            return
        # Drop the least recently seen entries; bounded memory under a spray attack.
        keys_by_last = sorted(self._buckets.items(), key=lambda kv: kv[1].last_seen)
        for key, _ in keys_by_last[: _MAX_TRACKED_KEYS // 10]:
            self._buckets.pop(key, None)
