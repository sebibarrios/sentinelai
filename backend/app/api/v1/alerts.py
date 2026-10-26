import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query, status
from pydantic import IPvAnyAddress
from sqlalchemy.orm import Session

from app.api.deps import Analyst, Viewer
from app.db.session import get_db
from app.detection.rules import RULES
from app.models import Alert, User
from app.models.enums import AlertStatus, Severity
from app.schemas.common import Page, PageParams
from app.schemas.security import (
    AlertDetail,
    AlertOut,
    AlertStatusUpdate,
    PromoteResult,
    RuleOut,
)
from app.services import alerts as svc

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("/rules", response_model=list[RuleOut])
def list_rules(_: User = Viewer) -> list[dict]:
    return [
        {"id": r.id, "name": r.name, "description": r.description, "severity": r.severity}
        for r in RULES
    ]


@router.get("", response_model=Page[AlertOut])
def list_alerts(
    severity: Severity | None = None,
    status_: AlertStatus | None = Query(None, alias="status"),
    rule_id: str | None = Query(None, max_length=20),
    src_ip: IPvAnyAddress | None = None,
    q: str | None = Query(None, max_length=100),
    upload_id: uuid.UUID | None = None,
    incident_id: uuid.UUID | None = None,
    since: datetime | None = Query(None, alias="from"),
    until: datetime | None = Query(None, alias="to"),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    _: User = Viewer,
    db: Session = Depends(get_db),
) -> dict:
    items, total = svc.list_alerts(
        db,
        PageParams(page=page, page_size=page_size),
        severity=severity,
        status=status_,
        rule_id=rule_id,
        src_ip=str(src_ip) if src_ip else None,
        q=q,
        upload_id=upload_id,
        incident_id=incident_id,
        since=since,
        until=until,
    )
    return {"items": items, "page": page, "page_size": page_size, "total": total}


@router.get("/{alert_id}", response_model=AlertDetail)
def get_alert(alert_id: uuid.UUID, _: User = Viewer, db: Session = Depends(get_db)) -> dict:
    alert = svc.get_alert(db, alert_id)
    evidence = svc.evidence_for(db, alert)
    return {
        **AlertOut.model_validate(alert).model_dump(),
        "rule_description": alert.rule_description,
        "evidence": evidence,
        "evidence_truncated": alert.event_count > len(evidence),
        "ai_analysis": svc.latest_analysis(db, "alert", alert.id),
    }


@router.patch("/{alert_id}", response_model=AlertOut)
def update_alert(
    alert_id: uuid.UUID,
    data: AlertStatusUpdate,
    _: User = Analyst,
    db: Session = Depends(get_db),
) -> Alert:
    return svc.set_status(db, svc.get_alert(db, alert_id), data.status)


@router.post(
    "/{alert_id}/promote", response_model=PromoteResult, status_code=status.HTTP_201_CREATED
)
def promote_alert(alert_id: uuid.UUID, user: User = Analyst, db: Session = Depends(get_db)) -> dict:
    incident = svc.promote(db, svc.get_alert(db, alert_id), user)
    return {"incident_id": incident.id, "reference": incident.reference}
