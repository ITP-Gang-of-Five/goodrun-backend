"""
Stops someone working out a password by trying lots of them.

Failed logins are counted per person (their IP address) rather than per account, so an
attacker can only ever lock themselves out. Counting per account alone would let anyone
lock a real user out just by typing their email in wrong a few times. Within LOCKOUT_WINDOW:
- MAX_FAILED_PER_ACCOUNT wrong passwords from one IP for one email locks that IP out of
  that email
- MAX_FAILED_PER_IP wrong passwords from one IP across any emails locks that IP out of
  logging in at all, so it can't just work through every account instead
Either way the login is refused with 429 TOO_MANY_LOGIN_ATTEMPTS, even with the right
password, until the oldest of those failures drops out of the window. Logging in
successfully clears that IP's count for that email.

NB: a shared network (e.g. uni wifi) is one IP, so someone else on it failing a lot can
lock out the rest of that network for a while. That's the price of not being able to
lock out an account from anywhere.

NB: the counts are kept in memory, so they reset whenever the server restarts and
wouldn't be shared if we ever ran more than one copy of the server. That's fine while
there is one server on Render.
"""

import math
import time
from collections.abc import Callable
from threading import Lock

from fastapi import Request

from app.errors import ApiError

MAX_FAILED_PER_ACCOUNT = 5
MAX_FAILED_PER_IP = 20
LOCKOUT_WINDOW = 15 * 60  # seconds

# past this many keys being tracked, the ones with no recent failures are thrown away,
# so made up emails and addresses can't make this grow forever
_PRUNE_AFTER = 1000


def client_ip(request: Request) -> str:
    """
    The address of whoever sent the request.

    In production every request comes through Render's proxy, so the connection is from
    the proxy rather than the person. The proxy puts the person's address first in
    X-Forwarded-For. A client can put a made up address in that header themselves, but
    the worst that does is dodge their own limit, it can't lock anybody else out.
    """
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


class LoginAttempts:
    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        # key -> when each recent failed attempt happened, oldest first
        self._failures: dict[str, list[float]] = {}
        # requests are handled on several threads at once
        self._lock = Lock()

    def check(self, ip: str, email: str) -> None:
        """Raises 429 if this IP has had too many failed attempts recently."""
        with self._lock:
            locked = [
                recent[0]
                for recent, limit in (
                    (self._recent(_account_key(ip, email)), MAX_FAILED_PER_ACCOUNT),
                    (self._recent(_ip_key(ip)), MAX_FAILED_PER_IP),
                )
                if len(recent) >= limit
            ]
            if not locked:
                return
            wait = max(locked) + LOCKOUT_WINDOW - self._clock()

        minutes = max(1, math.ceil(wait / 60))
        raise ApiError(
            429,
            "TOO_MANY_LOGIN_ATTEMPTS",
            f"Too many failed attempts, try again in {minutes} minute"
            + ("" if minutes == 1 else "s"),
        )

    def record_failure(self, ip: str, email: str) -> None:
        with self._lock:
            for key in (_account_key(ip, email), _ip_key(ip)):
                self._failures[key] = [*self._recent(key), self._clock()]
            if len(self._failures) > _PRUNE_AFTER:
                for stale in [k for k in self._failures if not self._recent(k)]:
                    del self._failures[stale]

    def clear(self, ip: str, email: str) -> None:
        with self._lock:
            self._failures.pop(_account_key(ip, email), None)

    def reset(self) -> None:
        """Forgets every failed attempt. Used between tests."""
        with self._lock:
            self._failures.clear()

    def _recent(self, key: str) -> list[float]:
        # the failures for this key that are still inside the window
        cutoff = self._clock() - LOCKOUT_WINDOW
        return [at for at in self._failures.get(key, []) if at > cutoff]


def _account_key(ip: str, email: str) -> str:
    # logins match emails ignoring case and surrounding spaces, so the count does too
    return f"{ip} {email.strip().lower()}"


def _ip_key(ip: str) -> str:
    return ip


# the one shared by every login request
login_attempts = LoginAttempts()
