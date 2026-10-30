"""
Sliding-window rate limit: N calls per 60 s per key (user id, or IP for guests).

In memory, so it is per backend process. That is enough for one Render
instance; several instances would need a shared store.
"""

import threading
import time
from collections import defaultdict, deque


class RateLimiter:
    def __init__(self, per_minute: int, window: float = 60.0):
        self.per_minute = per_minute
        self.window = window
        self._hits: dict[str, deque] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str, now: float | None = None) -> tuple[bool, int]:
        """(allowed, seconds until the next call would be allowed)."""
        now = time.monotonic() if now is None else now
        with self._lock:
            hits = self._hits[key]
            while hits and now - hits[0] >= self.window:
                hits.popleft()
            if len(hits) >= self.per_minute:
                return False, max(1, int(self.window - (now - hits[0])) + 1)
            hits.append(now)
            return True, 0
