"""Simple in-memory per-IP rate limiter (Phase 9).

Fixed 60-second window, keyed by (bucket, client IP). Limits are read
from the environment at call time so they can be tuned without code
changes (and monkeypatched deterministically in tests):

  RATE_LIMIT_AUTH_PER_MIN      — /auth/login + /auth/register (default 10)
  RATE_LIMIT_COMMANDS_PER_MIN  — /commands (default 60)

State is process-local (single-instance personal deployment). Use
`reset_rate_limits()` to clear all counters — tests rely on it via an
autouse fixture so the generous production limits never flake the suite.
"""
import os
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request, status

WINDOW_SECONDS = 60.0

_DEFAULTS = {"auth": 10, "commands": 60}
_ENV_VARS = {"auth": "RATE_LIMIT_AUTH_PER_MIN", "commands": "RATE_LIMIT_COMMANDS_PER_MIN"}

_hits: dict[str, deque[float]] = defaultdict(deque)


def _limit_for(bucket: str) -> int:
    raw = os.environ.get(_ENV_VARS[bucket])
    if raw:
        try:
            value = int(raw)
            if value > 0:
                return value
        except ValueError:
            pass
    return _DEFAULTS[bucket]


def reset_rate_limits() -> None:
    _hits.clear()


def check_rate_limit(request: Request, bucket: str) -> None:
    ip = request.client.host if request.client and request.client.host else "unknown"
    key = f"{bucket}:{ip}"
    now = time.monotonic()
    queue = _hits[key]
    while queue and queue[0] <= now - WINDOW_SECONDS:
        queue.popleft()
    limit = _limit_for(bucket)
    if len(queue) >= limit:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            f"Rate limit exceeded: at most {limit} requests per minute for this "
            "endpoint from one IP. Please wait a minute and try again.",
        )
    queue.append(now)


def rate_limit(bucket: str):
    """FastAPI dependency factory: `Depends(rate_limit('auth'))`."""

    def _dependency(request: Request) -> None:
        check_rate_limit(request, bucket)

    return _dependency
