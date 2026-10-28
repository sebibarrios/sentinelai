"""Sliding-window rate limits backed by PostgreSQL.

A limit is "at most N hits for this (scope, key) in the last W minutes". When it's
exceeded, the caller gets a 429 with a Retry-After header saying when the oldest
counted hit leaves the window.
"""

import math
from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import TooManyRequests
from app.core.proxy_auth import client_ip as _client_ip
from app.db.base import utcnow
from app.models.rate_limit import RateLimitHit

RETENTION = timedelta(days=1)


@dataclass(frozen=True)
class Limit:
    scope: str
    max_hits: int
    window: timedelta
    message: str


def login_failures_per_account() -> Limit:
    s = get_settings()
    return Limit(
        "login_fail_account",
        s.login_max_failures_per_account,
        timedelta(minutes=s.login_lockout_minutes),
        "Too many failed sign-in attempts for this account.",
    )


def login_failures_per_ip() -> Limit:
    s = get_settings()
    return Limit(
        "login_fail_ip",
        s.login_max_failures_per_ip,
        timedelta(minutes=s.login_lockout_minutes),
        "Too many failed sign-in attempts from your network.",
    )


def registrations_per_ip() -> Limit:
    s = get_settings()
    return Limit(
        "register_ip",
        s.register_max_per_ip_per_hour,
        timedelta(hours=1),
        "Too many accounts created from your network.",
    )


# Re-exported so routes import one place for rate-limit concerns.
client_ip = _client_ip


def check(db: Session, limit: Limit, key: str) -> None:
    """Raise 429 if the limit is already reached. Doesn't record anything."""
    since = utcnow() - limit.window
    count, oldest = db.execute(
        select(func.count(), func.min(RateLimitHit.created_at)).where(
            RateLimitHit.scope == limit.scope,
            RateLimitHit.key == key,
            RateLimitHit.created_at >= since,
        )
    ).one()
    if count >= limit.max_hits:
        retry_after = max(1, math.ceil((oldest + limit.window - utcnow()).total_seconds()))
        minutes = math.ceil(retry_after / 60)
        raise TooManyRequests(
            f"{limit.message} Try again in {minutes} minute{'s' if minutes != 1 else ''}.",
            headers={"Retry-After": str(retry_after)},
        )


def hit(db: Session, limit: Limit, key: str) -> None:
    """Record one hit and prune expired rows. Commits, so the hit survives a later error."""
    db.add(RateLimitHit(scope=limit.scope, key=key))
    db.execute(delete(RateLimitHit).where(RateLimitHit.created_at < utcnow() - RETENTION))
    db.commit()


def clear(db: Session, limit: Limit, key: str) -> None:
    db.execute(
        delete(RateLimitHit).where(RateLimitHit.scope == limit.scope, RateLimitHit.key == key)
    )
