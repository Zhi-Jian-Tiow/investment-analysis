"""BR-016 / EX-009: 5 failed login attempts within a 10-minute window from the
same IP locks further login attempts from that IP for 10 minutes. Counter
resets on a successful login from that IP.

No table in the physical schema tracks this (it isn't one of the 16 tables in
BursaTrack-DB-Stage3-Physical-Schema.md), so — consistent with architecture
P-002 ("no Redis; in-process state for anything that doesn't need to survive a
restart") — this is a simple in-process tracker, mirroring how SlowAPI's
in-memory rate limiter is already used elsewhere in this app.
"""

import time

FAILURE_THRESHOLD = 5
WINDOW_SECONDS = 10 * 60
LOCKOUT_SECONDS = 10 * 60


class LoginLockoutTracker:
    def __init__(self) -> None:
        self._failure_times: dict[str, list[float]] = {}
        self._locked_until: dict[str, float] = {}

    def seconds_until_unlocked(self, key: str) -> int | None:
        """Returns remaining lockout seconds, or None if not currently locked."""
        locked_until = self._locked_until.get(key)
        if locked_until is None:
            return None
        remaining = locked_until - time.monotonic()
        if remaining <= 0:
            self._locked_until.pop(key, None)
            self._failure_times.pop(key, None)
            return None
        return int(remaining) + 1

    def record_failure(self, key: str) -> None:
        now = time.monotonic()
        window_start = now - WINDOW_SECONDS
        attempts = [t for t in self._failure_times.get(key, []) if t >= window_start]
        attempts.append(now)
        self._failure_times[key] = attempts
        if len(attempts) >= FAILURE_THRESHOLD:
            self._locked_until[key] = now + LOCKOUT_SECONDS

    def record_success(self, key: str) -> None:
        self._failure_times.pop(key, None)
        self._locked_until.pop(key, None)

    def reset(self) -> None:
        """Test-only: clear all tracked state between test cases."""
        self._failure_times.clear()
        self._locked_until.clear()


tracker = LoginLockoutTracker()
