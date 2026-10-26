from enum import StrEnum


class Role(StrEnum):
    admin = "admin"
    analyst = "analyst"
    viewer = "viewer"


class Severity(StrEnum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class IncidentStatus(StrEnum):
    open = "open"
    investigating = "investigating"
    contained = "contained"
    resolved = "resolved"
    closed = "closed"


class HistoryAction(StrEnum):
    created = "created"
    updated = "updated"
    assigned = "assigned"
    status_changed = "status_changed"
    note_added = "note_added"
    alert_linked = "alert_linked"


SEVERITY_RANK = {Severity.low: 1, Severity.medium: 2, Severity.high: 3, Severity.critical: 4}


class UploadStatus(StrEnum):
    processing = "processing"
    completed = "completed"
    failed = "failed"


class EventCategory(StrEnum):
    auth = "auth"
    network = "network"


class EventOutcome(StrEnum):
    success = "success"
    failure = "failure"
    allowed = "allowed"
    denied = "denied"


class AlertStatus(StrEnum):
    open = "open"
    acknowledged = "acknowledged"
    dismissed = "dismissed"
    escalated = "escalated"  # promoted to an incident


class AiTarget(StrEnum):
    alert = "alert"
    incident = "incident"


class AiKind(StrEnum):
    alert_explanation = "alert_explanation"
    incident_report = "incident_report"
