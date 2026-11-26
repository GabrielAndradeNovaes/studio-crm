from __future__ import annotations

import time
from collections import defaultdict, deque
from threading import Lock

from fastapi import Request

from app.core.config import get_settings
from app.core.exceptions import RateLimitExceededError


class SlidingWindowRateLimiter:
    def __init__(self) -> None:
        self._buckets: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def check(self, key: str, *, max_requests: int, window_seconds: int) -> None:
        now = time.monotonic()
        cutoff = now - window_seconds
        with self._lock:
            bucket = self._buckets[key]
            while bucket and bucket[0] <= cutoff:
                bucket.popleft()
            if len(bucket) >= max_requests:
                raise RateLimitExceededError()
            bucket.append(now)

    def reset(self) -> None:
        with self._lock:
            self._buckets.clear()


rate_limiter = SlidingWindowRateLimiter()


def get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def rate_limit_auth(scope: str):
    async def _dependency(request: Request) -> None:
        settings = get_settings()
        client_ip = get_client_ip(request)
        key = f"{scope}:{client_ip}"
        rate_limiter.check(
            key,
            max_requests=settings.AUTH_RATE_LIMIT_REQUESTS,
            window_seconds=settings.AUTH_RATE_LIMIT_WINDOW_SECONDS,
        )

    return _dependency
