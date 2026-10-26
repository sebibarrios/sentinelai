from datetime import timedelta
from typing import Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import Viewer
from app.db.base import utcnow
from app.db.session import get_db
from app.models import Incident, User
from app.models.enums import IncidentStatus, Severity
from app.schemas.incident import IncidentOut

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

_RANGES = {"24h": timedelta(hours=24), "7d": timedelta(days=7), "30d": timedelta(days=30)}
_OPEN_STATES = [IncidentStatus.open, IncidentStatus.investigating, IncidentStatus.contained]


class DashboardSummary(BaseModel):
    range: str
    open_incidents: int
    critical_open_incidents: int
    incidents_in_range: int
    incidents_by_status: dict[str, int]
    incidents_by_severity: dict[str, int]
    recent_incidents: list[IncidentOut]


@router.get("/summary", response_model=DashboardSummary)
def summary(
    range_: Literal["24h", "7d", "30d"] = Query("7d", alias="range"),
    _: User = Viewer,
    db: Session = Depends(get_db),
) -> dict:
    since = utcnow() - _RANGES[range_]

    by_status = dict.fromkeys((s.value for s in IncidentStatus), 0)
    for status, count in db.execute(
        select(Incident.status, func.count()).group_by(Incident.status)
    ):
        by_status[status.value] = count

    by_severity = dict.fromkeys((s.value for s in Severity), 0)
    for severity, count in db.execute(
        select(Incident.severity, func.count())
        .where(Incident.status.in_(_OPEN_STATES))
        .group_by(Incident.severity)
    ):
        by_severity[severity.value] = count

    in_range = (
        db.scalar(select(func.count()).select_from(Incident).where(Incident.created_at >= since))
        or 0
    )
    recent = db.scalars(select(Incident).order_by(Incident.created_at.desc()).limit(5)).all()

    return {
        "range": range_,
        "open_incidents": sum(by_status[s.value] for s in _OPEN_STATES),
        "critical_open_incidents": by_severity[Severity.critical.value],
        "incidents_in_range": in_range,
        "incidents_by_status": by_status,
        "incidents_by_severity": by_severity,
        "recent_incidents": list(recent),
    }
