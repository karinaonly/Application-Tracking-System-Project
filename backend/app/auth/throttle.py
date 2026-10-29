"""E3: in-process brute-force protection for the login endpoint.

A local instance has no shared cache or Redis, so a small in-memory sliding
window is enough: after ``MAX_FAILURES`` failed attempts for the same
email + client key inside ``WINDOW_SECONDS``, further attempts are rejected
with a 429 until the oldest failure ages out.

The state is intentionally process-local. Restarting the backend clears it,
which is acceptable for a single-user app; a multi-instance deployment would
need a shared store instead.
"""

import time

# Five wrong passwords in fifteen minutes is far above a human typo rate and
# far below a useful guessing rate for an 8+ character password.
MAX_FAILURES = 5
WINDOW_SECONDS = 15 * 60


class LoginThrottle:
    """Sliding-window failure counter keyed by ``email|client``."""

    def __init__(
        self,
        max_failures: int = MAX_FAILURES,
        window_seconds: int = WINDOW_SECONDS,
    ):
        self.max_failures = max_failures
        self.window_seconds = window_seconds
        self._failures: dict[str, list[float]] = {}

    def _recent(self, key: str, now: float) -> list[float]:
        attempts = [
            stamp for stamp in self._failures.get(key, [])
            if now - stamp < self.window_seconds
        ]
        if attempts:
            self._failures[key] = attempts
        else:
            self._failures.pop(key, None)
        return attempts

    def retry_after(self, key: str, now: float | None = None) -> int:
        """Seconds until the caller may try again (0 = allowed right now)."""
        now = time.monotonic() if now is None else now
        attempts = self._recent(key, now)
        if len(attempts) < self.max_failures:
            return 0
        # The lock lifts when the oldest counted failure leaves the window.
        return max(1, int(self.window_seconds - (now - attempts[0])))

    def record_failure(self, key: str, now: float | None = None) -> None:
        now = time.monotonic() if now is None else now
        attempts = self._recent(key, now)
        attempts.append(now)
        self._failures[key] = attempts

    def reset(self, key: str) -> None:
        self._failures.pop(key, None)

    def clear(self) -> None:
        """Drop all state (tests, or an operator unlocking an account)."""
        self._failures.clear()


# One throttle for the whole process so every request shares the counters.
login_throttle = LoginThrottle()


def throttle_key(email: str, client: str | None) -> str:
    """Throttle per email *and* client, so one address cannot lock out others."""
    return f"{(email or '').strip().lower()}|{(client or 'unknown').strip().lower()}"
