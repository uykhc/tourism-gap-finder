"""Small fixed-window limiter for the single-worker pilot deployment."""

from __future__ import annotations

import os
import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request


class FixedWindowRateLimiter:
    def __init__(self) -> None:
        self._events: dict[tuple[str, str], deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, request: Request, action: str) -> None:
        limit = int(os.getenv("AUTH_RATE_LIMIT_PER_MINUTE", "10"))
        if limit <= 0:
            return
        forwarded = request.headers.get("x-forwarded-for", "").split(",", 1)[0].strip()
        host = forwarded or (request.client.host if request.client else "unknown")
        now = time.monotonic()
        key = (action, host)
        with self._lock:
            events = self._events[key]
            while events and events[0] <= now - 60:
                events.popleft()
            if len(events) >= limit:
                raise HTTPException(429, detail="Too many authentication attempts")
            events.append(now)


auth_rate_limiter = FixedWindowRateLimiter()
