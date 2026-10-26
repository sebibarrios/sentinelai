"""Incident business logic. Every change writes an audit row in the same transaction."""

import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.errors import AppError, NotFound
from app.db.base import utcnow
from app.models import Incident, IncidentHistory, IncidentNote, User
from app.models.enums import HistoryAction, IncidentStatus, Role, Severity
from app.schemas.common import PageParams
from app.schemas.incident import IncidentCreate, IncidentUpdate

_CLOSED_STATES = {IncidentStatus.resolved, IncidentStatus.closed}


def _audit(
    db: Session,
    incident: Incident,
    actor: User,
    action: HistoryAction,
    field: str | None = None,
    old: object = None,
    new: object = None,
) -> None:
    db.add(
        IncidentHistory(
            incident_id=incident.id,
            actor_id=actor.id,
            action=action,
            field=field,
            old_value=None if old is None else str(old),
            new_value=None if new is None else str(new),
        )
    )


# Public name for other services (e.g. linking an alert) to write audit entries.
record = _audit


def _validate_assignee(db: Session, assignee_id: uuid.UUID | None) -> User | None:
    if assignee_id is None:
        return None
    user = db.get(User, assignee_id)
    if user is None or not user.is_active:
        raise AppError("Assignee not found or inactive")
    if user.role == Role.viewer:
        raise AppError("Incidents can only be assigned to analysts or admins")
    return user


def get_incident(db: Session, incident_id: uuid.UUID) -> Incident:
    incident = db.get(Incident, incident_id)
    if incident is None:
        raise NotFound("Incident not found")
    return incident


def list_incidents(
    db: Session,
    page: PageParams,
    *,
    status: IncidentStatus | None = None,
    severity: Severity | None = None,
    assignee_id: uuid.UUID | None = None,
    q: str | None = None,
) -> tuple[list[Incident], int]:
    stmt = select(Incident)
    if status:
        stmt = stmt.where(Incident.status == status)
    if severity:
        stmt = stmt.where(Incident.severity == severity)
    if assignee_id:
        stmt = stmt.where(Incident.assignee_id == assignee_id)
    if q:
        # Parameterized ILIKE; escape wildcards so user input is matched literally.
        term = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        pattern = f"%{term}%"
        stmt = stmt.where(
            or_(
                Incident.title.ilike(pattern, escape="\\"),
                Incident.description.ilike(pattern, escape="\\"),
            )
        )
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(
        stmt.order_by(Incident.created_at.desc()).offset(page.offset).limit(page.page_size)
    ).all()
    return list(rows), total


def create_incident(db: Session, data: IncidentCreate, actor: User) -> Incident:
    _validate_assignee(db, data.assignee_id)
    incident = Incident(
        title=data.title.strip(),
        description=data.description,
        severity=data.severity,
        assignee_id=data.assignee_id,
        created_by_id=actor.id,
    )
    db.add(incident)
    db.flush()  # assigns id and number
    _audit(db, incident, actor, HistoryAction.created, new=incident.reference)
    db.commit()
    db.refresh(incident)
    return incident


def update_incident(db: Session, incident: Incident, data: IncidentUpdate, actor: User) -> Incident:
    changes = data.model_dump(exclude_unset=True)

    if "assignee_id" in changes and changes["assignee_id"] != incident.assignee_id:
        new_assignee = _validate_assignee(db, changes["assignee_id"])
        old_name = incident.assignee.full_name if incident.assignee else None
        incident.assignee_id = changes["assignee_id"]
        _audit(
            db,
            incident,
            actor,
            HistoryAction.assigned,
            "assignee",
            old_name,
            new_assignee.full_name if new_assignee else None,
        )

    if "status" in changes and changes["status"] and changes["status"] != incident.status:
        old_status = incident.status
        incident.status = changes["status"]
        if incident.status in _CLOSED_STATES and incident.closed_at is None:
            incident.closed_at = utcnow()
        elif incident.status not in _CLOSED_STATES:
            incident.closed_at = None  # reopened
        _audit(
            db,
            incident,
            actor,
            HistoryAction.status_changed,
            "status",
            old_status.value,
            incident.status.value,
        )

    for field in ("title", "description", "severity"):
        if field in changes and changes[field] is not None:
            old = getattr(incident, field)
            new = changes[field]
            if old != new:
                setattr(incident, field, new)
                _audit(
                    db,
                    incident,
                    actor,
                    HistoryAction.updated,
                    field,
                    getattr(old, "value", old),
                    getattr(new, "value", new),
                )

    db.commit()
    db.refresh(incident)
    return incident


def add_note(db: Session, incident: Incident, body: str, actor: User) -> IncidentNote:
    note = IncidentNote(incident_id=incident.id, author_id=actor.id, body=body.strip())
    db.add(note)
    _audit(db, incident, actor, HistoryAction.note_added)
    incident.updated_at = utcnow()
    db.commit()
    db.refresh(note)
    return note


def get_history(db: Session, incident: Incident) -> list[IncidentHistory]:
    return list(
        db.scalars(
            select(IncidentHistory)
            .where(IncidentHistory.incident_id == incident.id)
            .order_by(IncidentHistory.created_at, IncidentHistory.id)
        ).all()
    )
