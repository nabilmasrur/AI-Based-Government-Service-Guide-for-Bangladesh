"""Per-IP rate limiting.

The public deployment runs on a free Gemini tier with a shared daily quota. Without
this, one person holding down enter can exhaust the quota for everybody — including
during the lab demo.
"""
from __future__ import annotations

import time
from collections import defaultdict, deque

from . import config

_minute: dict[str, deque] = defaultdict(deque)
_day: dict[str, deque] = defaultdict(deque)


def check(ip: str) -> tuple[bool, str]:
    """Returns (allowed, reason). Only calls that reach Gemini should be counted."""
    now = time.time()

    bucket = _minute[ip]
    while bucket and now - bucket[0] > 60:
        bucket.popleft()
    if len(bucket) >= config.RATE_PER_MIN:
        return False, "per-minute"

    daily = _day[ip]
    while daily and now - daily[0] > 86400:
        daily.popleft()
    if len(daily) >= config.RATE_PER_DAY:
        return False, "per-day"

    bucket.append(now)
    daily.append(now)
    return True, ""


def remaining(ip: str) -> dict:
    """How much of this client's allowance is left — shown in the UI so a user
    who is about to be cut off can see it coming."""
    now = time.time()
    used_min = sum(1 for t in _minute.get(ip, ()) if now - t <= 60)
    used_day = sum(1 for t in _day.get(ip, ()) if now - t <= 86400)
    return {
        "minute_left": max(0, config.RATE_PER_MIN - used_min),
        "minute_max": config.RATE_PER_MIN,
        "day_left": max(0, config.RATE_PER_DAY - used_day),
        "day_max": config.RATE_PER_DAY,
    }


def snapshot() -> dict:
    return {"tracked_ips": len(_minute),
            "per_min": config.RATE_PER_MIN,
            "per_day": config.RATE_PER_DAY}
