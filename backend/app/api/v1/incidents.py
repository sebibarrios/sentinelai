import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import Analyst, Viewer
from app.db.session import get_db
from app.models import Incident, IncidentHistory, IncidentNote, User
from app.models.enums import IncidentStatus, Severity
from app.schemas.common import Page, PageParams
from app.schemas.incident import (
    HistoryOut,
    IncidentCreate,
    IncidentDetail,
    IncidentOut,
    IncidentUpdate,
    NoteCreate,
    NoteOut,
)
from app.services import incidents as svc

router = APIRouter(prefix="/incidents", tags=["incidents"])


@router.get("", response_model=Page[IncidentOut])
def list_incidents(
    status_: IncidentStatus | None = Query(None, alias="status"),
    severity: Severity | None = None,
    assignee_id: uuid.UUID | None = None,
    q: str | None = Query(None, max_length=100),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    _: User = Viewer,
    db: Session = Depends(get_db),
) -> dict:
    params = PageParams(page=page, page_size=page_size)
    items, total = svc.list_incidents(
        db, params, status=status_, severity=severity, assignee_id=assignee_id, q=q
    )
    return {"items": items, "page": page, "page_size": page_size, "total": total}


@router.post("", response_model=IncidentOut, status_code=status.HTTP_201_CREATED)
def create_incident(
    data: IncidentCreate, user: User = Analyst, db: Session = Depends(get_db)
) -> Incident:
    return svc.create_incident(db, data, user)


@router.get("/{incident_id}", response_model=IncidentDetail)
def get_incident(
    incident_id: uuid.UUID, _: User = Viewer, db: Session = Depends(get_db)
) -> Incident:
    return svc.get_incident(db, incident_id)


@router.patch("/{incident_id}", response_model=IncidentOut)
def update_incident(
    incident_id: uuid.UUID,
    data: IncidentUpdate,
    user: User = Analyst,
    db: Session = Depends(get_db),
) -> Incident:
    incident = svc.get_incident(db, incident_id)
    return svc.update_incident(db, incident, data, user)


@router.post("/{incident_id}/notes", response_model=NoteOut, status_code=status.HTTP_201_CREATED)
def add_note(
    incident_id: uuid.UUID,
    data: NoteCreate,
    user: User = Analyst,
    db: Session = Depends(get_db),
) -> IncidentNote:
    incident = svc.get_incident(db, incident_id)
    return svc.add_note(db, incident, data.body, user)


@router.get("/{incident_id}/history", response_model=list[HistoryOut])
def get_history(
    incident_id: uuid.UUID, _: User = Viewer, db: Session = Depends(get_db)
) -> list[IncidentHistory]:
    return svc.get_history(db, svc.get_incident(db, incident_id))
