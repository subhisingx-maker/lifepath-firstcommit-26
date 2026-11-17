"""Tiny in-memory sliding-window rate limiter for expensive (AI) endpoints.

Limitation (documented): state lives in one process. With several server
processes each has its own counters. Use a shared store (e.g. Redis) if the
app is ever scaled out.
"""
from __future__ import annotations

import time
from collections import defaultdict, deque
from typing import Callable, Deque, Dict, Tuple


class SlidingWindowLimiter:
    def __init__(self, max_calls: int, window_seconds: float = 60.0,
                 clock: Callable[[], float] = time.monotonic) -> None:
        self.max_calls, self.window, self._clock = max_calls, window_seconds, clock
        self._hits: Dict[str, Deque[float]] = defaultdict(deque)

    def check(self, key: str) -> Tuple[bool, int]:
        """Return (allowed, retry_after_seconds). Records the call when allowed."""
        now = self._clock()
        hits = self._hits[key]
        while hits and now - hits[0] >= self.window:
            hits.popleft()
        if len(hits) >= self.max_calls:
            return False, max(1, int(self.window - (now - hits[0])) + 1)
        hits.append(now)
        return True, 0
