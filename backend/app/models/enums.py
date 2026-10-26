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
