"""Sliding-window rate limits backed by PostgreSQL.

A limit is "at most N hits for this (scope, key) in the last W minutes". When it's
exceeded, the caller gets a 429 with a Retry-After header saying when the oldest
counted hit leaves the window.
"""

import math
from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import delete, func, select, text
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


def ai_requests_site_wide() -> Limit:
    return Limit(
        "ai_site_wide",
        get_settings().ai_requests_per_day_site_wide,
        timedelta(hours=24),
        "The demo's daily AI budget is used up.",
    )


def password_change_failures_per_user() -> Limit:
    s = get_settings()
    return Limit(
        "password_change_fail",
        s.login_max_failures_per_account,
        timedelta(minutes=s.login_lockout_minutes),
        "Too many incorrect current-password attempts.",
    )


def _lock(db: Session, limit: Limit, key: str) -> None:
    """Serialize work on one (scope, key) until the transaction ends.

    pg_advisory_xact_lock is released automatically on commit or rollback, so it's held
    only for the brief count-and-insert in reserve(), never during password hashing.
    """
    db.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:k, 0))"),
        {"k": f"{limit.scope}:{key}"},
    )


def _check(db: Session, limit: Limit, key: str) -> None:
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


def reserve(db: Session, limit: Limit, key: str) -> int:
    """Atomically check the limit and count this attempt *before* doing the work.

    Counting up front (rather than after a failure) means attempts still in flight
    count too, so simultaneous requests can't all slip under the limit. Call release()
    if the attempt succeeds. The caller commits; that also releases the lock.
    Raises 429 if the limit is already reached.
    """
    _lock(db, limit, key)
    _check(db, limit, key)
    hit = RateLimitHit(scope=limit.scope, key=key)
    db.add(hit)
    db.flush()
    return hit.id


def release(db: Session, hit_id: int | None) -> None:
    """Uncount a reserved attempt that turned out to be legitimate."""
    if hit_id is not None:
        db.execute(delete(RateLimitHit).where(RateLimitHit.id == hit_id))


def clear(db: Session, limit: Limit, key: str) -> None:
    db.execute(
        delete(RateLimitHit).where(RateLimitHit.scope == limit.scope, RateLimitHit.key == key)
    )


def prune(db: Session) -> None:
    db.execute(delete(RateLimitHit).where(RateLimitHit.created_at < utcnow() - RETENTION))
