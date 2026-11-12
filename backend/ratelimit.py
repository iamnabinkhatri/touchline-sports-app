"""In-memory sliding-window rate limiter (single-process).

For multi-instance deployments, enforce the same limits at the reverse
proxy / API gateway or back this class with Redis.
"""
import threading
import time
from collections import defaultdict, deque


class RateLimiter:
    def __init__(self, clock=time.monotonic):
        self._clock = clock
        self._events = defaultdict(deque)
        self._lock = threading.Lock()

    def _prune(self, key, window):
        events = self._events[key]
        cutoff = self._clock() - window
        while events and events[0] <= cutoff:
            events.popleft()
        if not events:
            self._events.pop(key, None)
            return deque()
        return events

    def retry_after(self, key, limit, window):
        """Seconds until `key` may try again, or 0 if it is under the limit."""
        with self._lock:
            events = self._prune(key, window)
            if len(events) < limit:
                return 0
            return max(1, int(events[0] + window - self._clock()) + 1)

    def record(self, key, window):
        with self._lock:
            self._prune(key, window)
            self._events[key].append(self._clock())

    def clear(self, key):
        with self._lock:
            self._events.pop(key, None)

    def reset(self):
        with self._lock:
            self._events.clear()


limiter = RateLimiter()
