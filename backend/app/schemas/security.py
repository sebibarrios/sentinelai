import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, IPvAnyAddress

from app.models.enums import AlertStatus, EventCategory, EventOutcome, Severity, UploadStatus
from app.schemas.common import ORMModel
from app.schemas.user import UserBrief


class UploadOut(ORMModel):
    id: uuid.UUID
    original_filename: str
    format: str
    size_bytes: int
    status: UploadStatus
    rows_total: int
    rows_parsed: int
    rows_rejected: int
    alerts_created: int
    rejection_samples: list[dict[str, Any]]
    processing_ms: int | None
    uploaded_by: UserBrief
    created_at: datetime
    completed_at: datetime | None


class EventOut(ORMModel):
    id: int
    upload_id: uuid.UUID
    occurred_at: datetime
    category: EventCategory
    action: str
    outcome: EventOutcome
    username: str | None
    src_ip: IPvAnyAddress
    dst_ip: IPvAnyAddress | None
    dst_port: int | None
    protocol: str | None
    user_agent: str | None
    country: str | None


class AlertOut(ORMModel):
    id: uuid.UUID
    rule_id: str
    rule_name: str
    title: str
    severity: Severity
    status: AlertStatus
    src_ip: IPvAnyAddress | None
    username: str | None
    first_seen: datetime
    last_seen: datetime
    event_count: int
    details: dict[str, Any]
    upload_id: uuid.UUID
    incident_id: uuid.UUID | None
    created_at: datetime


class AiAnalysisOut(ORMModel):
    id: uuid.UUID
    kind: str
    model: str
    prompt_version: str
    output: dict[str, Any]
    requested_by: UserBrief
    created_at: datetime


class AlertDetail(AlertOut):
    rule_description: str
    evidence: list[EventOut]
    evidence_truncated: bool
    ai_analysis: AiAnalysisOut | None


class AlertStatusUpdate(BaseModel):
    status: AlertStatus


class PromoteResult(BaseModel):
    incident_id: uuid.UUID
    reference: str


class RuleOut(BaseModel):
    id: str
    name: str
    description: str
    severity: Severity
