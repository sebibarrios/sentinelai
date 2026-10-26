import uuid
from datetime import datetime

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.errors import AppError, Conflict, NotFound
from app.models import AiAnalysis, Alert, AlertEvent, Incident, SecurityEvent, User
from app.models.enums import AlertStatus, HistoryAction, Severity
from app.schemas.common import PageParams
from app.schemas.incident import IncidentCreate
from app.services import incidents as incident_svc

EVIDENCE_LIMIT = 200


def _escape_like(q: str) -> str:
    return "%" + q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


def get_alert(db: Session, alert_id: uuid.UUID) -> Alert:
    alert = db.get(Alert, alert_id)
    if alert is None:
        raise NotFound("Alert not found")
    return alert


def list_alerts(
    db: Session,
    page: PageParams,
    *,
    severity: Severity | None = None,
    status: AlertStatus | None = None,
    rule_id: str | None = None,
    src_ip: str | None = None,
    q: str | None = None,
    upload_id: uuid.UUID | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
) -> tuple[list[Alert], int]:
    stmt = select(Alert)
    if severity:
        stmt = stmt.where(Alert.severity == severity)
    if status:
        stmt = stmt.where(Alert.status == status)
    if rule_id:
        stmt = stmt.where(Alert.rule_id == rule_id)
    if src_ip:
        stmt = stmt.where(Alert.src_ip == src_ip)
    if upload_id:
        stmt = stmt.where(Alert.upload_id == upload_id)
    if since:
        stmt = stmt.where(Alert.last_seen >= since)
    if until:
        stmt = stmt.where(Alert.first_seen <= until)
    if q:
        pattern = _escape_like(q)
        stmt = stmt.where(
            or_(
                Alert.title.ilike(pattern, escape="\\"),
                Alert.username.ilike(pattern, escape="\\"),
            )
        )
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(
        stmt.order_by(Alert.first_seen.desc(), Alert.id).offset(page.offset).limit(page.page_size)
    ).all()
    return list(rows), total


def evidence_for(db: Session, alert: Alert) -> list[SecurityEvent]:
    return list(
        db.scalars(
            select(SecurityEvent)
            .join(AlertEvent, AlertEvent.event_id == SecurityEvent.id)
            .where(AlertEvent.alert_id == alert.id)
            .order_by(SecurityEvent.occurred_at, SecurityEvent.id)
            .limit(EVIDENCE_LIMIT)
        ).all()
    )


def latest_analysis(db: Session, target_type: str, target_id: uuid.UUID) -> AiAnalysis | None:
    return db.scalar(
        select(AiAnalysis)
        .where(
            AiAnalysis.target_type == target_type,
            AiAnalysis.target_id == target_id,
        )
        .order_by(AiAnalysis.created_at.desc())
        .limit(1)
    )


def set_status(db: Session, alert: Alert, status: AlertStatus) -> Alert:
    if alert.incident_id and status != AlertStatus.escalated:
        raise AppError("This alert is linked to an incident; manage it from the incident.")
    if status == AlertStatus.escalated and not alert.incident_id:
        raise AppError("Use 'Promote to incident' to escalate an alert.")
    alert.status = status
    db.commit()
    db.refresh(alert)
    return alert


def _describe(alert: Alert) -> str:
    lines = [
        f"Promoted from alert {alert.rule_id} ({alert.rule_name}).",
        "",
        "Verified facts from detection:",
        f"- {alert.title}",
        f"- Events: {alert.event_count}, from {alert.first_seen:%Y-%m-%d %H:%M} "
        f"to {alert.last_seen:%Y-%m-%d %H:%M} UTC",
    ]
    if alert.src_ip:
        lines.append(f"- Source IP: {alert.src_ip}")
    if alert.username:
        lines.append(f"- Account: {alert.username}")
    for key, value in alert.details.items():
        lines.append(f"- {key.replace('_', ' ').capitalize()}: {value}")
    return "\n".join(lines)


def promote(db: Session, alert: Alert, actor: User) -> Incident:
    if alert.incident_id:
        incident = db.get(Incident, alert.incident_id)
        raise Conflict(
            "This alert is already linked to an incident.",
            details={
                "incident_id": str(alert.incident_id),
                "reference": incident.reference if incident else None,
            },
        )
    incident = incident_svc.create_incident(
        db,
        IncidentCreate(
            title=alert.title[:200],
            description=_describe(alert),
            severity=alert.severity,
            assignee_id=actor.id if actor.role != "viewer" else None,
        ),
        actor,
    )
    alert.incident_id = incident.id
    alert.status = AlertStatus.escalated
    incident_svc.record(
        db, incident, actor, HistoryAction.alert_linked, "alert", None, alert.rule_id
    )
    db.commit()
    return incident
