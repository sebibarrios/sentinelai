import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.enums import HistoryAction, IncidentStatus, Severity
from app.schemas.common import ORMModel
from app.schemas.user import UserBrief


class IncidentCreate(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    description: str = Field("", max_length=10_000)
    severity: Severity
    assignee_id: uuid.UUID | None = None


class IncidentUpdate(BaseModel):
    """All fields optional; only provided fields change (PATCH semantics)."""

    title: str | None = Field(None, min_length=3, max_length=200)
    description: str | None = Field(None, max_length=10_000)
    severity: Severity | None = None
    status: IncidentStatus | None = None
    assignee_id: uuid.UUID | None = None


class NoteCreate(BaseModel):
    body: str = Field(min_length=1, max_length=10_000)


class NoteOut(ORMModel):
    id: uuid.UUID
    body: str
    created_at: datetime
    author: UserBrief


class IncidentOut(ORMModel):
    id: uuid.UUID
    reference: str
    title: str
    description: str
    severity: Severity
    status: IncidentStatus
    assignee: UserBrief | None
    created_by: UserBrief
    created_at: datetime
    updated_at: datetime
    closed_at: datetime | None


class IncidentDetail(IncidentOut):
    notes: list[NoteOut]


class HistoryOut(ORMModel):
    id: int
    action: HistoryAction
    field: str | None
    old_value: str | None
    new_value: str | None
    created_at: datetime
    actor: UserBrief
