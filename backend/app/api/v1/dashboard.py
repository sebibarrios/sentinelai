from datetime import datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, IPvAnyAddress
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.api.deps import Viewer
from app.db.base import utcnow
from app.db.session import get_db
from app.models import Alert, Incident, SecurityEvent, User
from app.models.enums import AlertStatus, IncidentStatus, Severity
from app.schemas.incident import IncidentOut
from app.schemas.security import AlertOut

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

Range = Literal["24h", "7d", "30d"]
_RANGES: dict[str, tuple[timedelta, str, timedelta]] = {
    # range -> (length, bucket unit for date_trunc, bucket size)
    "24h": (timedelta(hours=24), "hour", timedelta(hours=1)),
    "7d": (timedelta(days=7), "day", timedelta(days=1)),
    "30d": (timedelta(days=30), "day", timedelta(days=1)),
}
_OPEN_INCIDENT = [IncidentStatus.open, IncidentStatus.investigating, IncidentStatus.contained]
_OPEN_ALERT = [AlertStatus.open, AlertStatus.acknowledged]


class TimelinePoint(BaseModel):
    bucket: datetime
    low: int = 0
    medium: int = 0
    high: int = 0
    critical: int = 0


class SourceCount(BaseModel):
    ip: IPvAnyAddress
    alerts: int
    max_severity: Severity


class DashboardSummary(BaseModel):
    range: Range
    # Incidents
    open_incidents: int
    critical_open_incidents: int
    incidents_in_range: int
    incidents_by_status: dict[str, int]
    incidents_by_severity: dict[str, int]
    recent_incidents: list[IncidentOut]
    # Alerts and events (event time, not ingest time)
    open_alerts: int
    open_alerts_by_severity: dict[str, int]
    alerts_in_range: int
    events_in_range: int
    alert_timeline: list[TimelinePoint]
    top_sources: list[SourceCount]
    recent_alerts: list[AlertOut]


def _counts_by(db: Session, column, *where) -> dict[str, int]:
    out = dict.fromkeys((s.value for s in Severity), 0) if column.key == "severity" else {}
    for key, count in db.execute(select(column, func.count()).where(*where).group_by(column)):
        out[key.value] = count
    return out


@router.get("/summary", response_model=DashboardSummary)
def summary(
    range_: Range = Query("7d", alias="range"),
    _: User = Viewer,
    db: Session = Depends(get_db),
) -> dict:
    length, unit, step = _RANGES[range_]
    now = utcnow()
    since = now - length

    # --- incidents ---
    by_status = dict.fromkeys((s.value for s in IncidentStatus), 0)
    by_status.update(_counts_by(db, Incident.status))
    inc_by_sev = _counts_by(db, Incident.severity, Incident.status.in_(_OPEN_INCIDENT))
    incidents_in_range = (
        db.scalar(select(func.count()).select_from(Incident).where(Incident.created_at >= since))
        or 0
    )
    recent_incidents = db.scalars(
        select(Incident).order_by(Incident.created_at.desc()).limit(5)
    ).all()

    # --- alerts ---
    alert_by_sev = _counts_by(db, Alert.severity, Alert.status.in_(_OPEN_ALERT))
    alerts_in_range = (
        db.scalar(select(func.count()).select_from(Alert).where(Alert.first_seen >= since)) or 0
    )
    events_in_range = (
        db.scalar(
            select(func.count())
            .select_from(SecurityEvent)
            .where(SecurityEvent.occurred_at >= since)
        )
        or 0
    )

    # Timeline: alerts per bucket per severity, zero-filled so the chart has no gaps.
    bucket_col = func.date_trunc(unit, Alert.first_seen).label("bucket")
    start = since.replace(minute=0, second=0, microsecond=0)
    if unit == "day":
        start = start.replace(hour=0)
    buckets: dict[datetime, dict] = {}
    t = start
    while t <= now:
        buckets[t] = {"bucket": t}
        t += step
    for bucket, severity, count in db.execute(
        select(bucket_col, Alert.severity, func.count())
        .where(Alert.first_seen >= start)
        .group_by(bucket_col, Alert.severity)
    ):
        key = bucket if bucket.tzinfo else bucket.replace(tzinfo=now.tzinfo)
        if key in buckets:
            buckets[key][severity.value] = count

    # Top sources by number of alerts in range; worst severity shown alongside.
    rank = func.max(
        case(
            (Alert.severity == Severity.critical, 4),
            (Alert.severity == Severity.high, 3),
            (Alert.severity == Severity.medium, 2),
            else_=1,
        )
    )
    top_rows = db.execute(
        select(Alert.src_ip, func.count().label("n"), rank.label("worst"))
        .where(Alert.first_seen >= since, Alert.src_ip.is_not(None))
        .group_by(Alert.src_ip)
        .order_by(func.count().desc(), rank.desc())
        .limit(5)
    ).all()
    sev_by_rank = {1: "low", 2: "medium", 3: "high", 4: "critical"}

    recent_alerts = db.scalars(select(Alert).order_by(Alert.first_seen.desc()).limit(6)).all()

    return {
        "range": range_,
        "open_incidents": sum(by_status[s.value] for s in _OPEN_INCIDENT),
        "critical_open_incidents": inc_by_sev[Severity.critical.value],
        "incidents_in_range": incidents_in_range,
        "incidents_by_status": by_status,
        "incidents_by_severity": inc_by_sev,
        "recent_incidents": list(recent_incidents),
        "open_alerts": sum(alert_by_sev.values()),
        "open_alerts_by_severity": alert_by_sev,
        "alerts_in_range": alerts_in_range,
        "events_in_range": events_in_range,
        "alert_timeline": list(buckets.values()),
        "top_sources": [
            {"ip": ip, "alerts": n, "max_severity": sev_by_rank[worst]} for ip, n, worst in top_rows
        ],
        "recent_alerts": list(recent_alerts),
    }
