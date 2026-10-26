"""Uploads, normalized events, and the alerts detection rules produce from them."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Identity,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import INET, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, UUIDPrimaryKey, utcnow
from app.models.enums import (
    AlertStatus,
    EventCategory,
    EventOutcome,
    Severity,
    UploadStatus,
)
from app.models.user import User


class LogUpload(UUIDPrimaryKey, Base):
    __tablename__ = "log_uploads"

    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)  # display only
    format: Mapped[str] = mapped_column(String(10), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    status: Mapped[UploadStatus] = mapped_column(
        Enum(UploadStatus, name="upload_status"), nullable=False
    )
    rows_total: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    rows_parsed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    rows_rejected: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    alerts_created: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    rejection_samples: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, default=list, nullable=False
    )
    processing_ms: Mapped[int | None] = mapped_column(Integer)
    uploaded_by_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True, nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    uploaded_by: Mapped[User] = relationship(lazy="joined")


class SecurityEvent(Base):
    __tablename__ = "security_events"
    __table_args__ = (
        Index("ix_security_events_src_ip_occurred_at", "src_ip", "occurred_at"),
        Index("ix_security_events_username_occurred_at", "username", "occurred_at"),
        CheckConstraint("dst_port BETWEEN 0 AND 65535", name="dst_port_range"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    upload_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("log_uploads.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), index=True, nullable=False
    )
    category: Mapped[EventCategory] = mapped_column(
        Enum(EventCategory, name="event_category"), nullable=False
    )
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    outcome: Mapped[EventOutcome] = mapped_column(
        Enum(EventOutcome, name="event_outcome"), nullable=False
    )
    username: Mapped[str | None] = mapped_column(String(128))
    src_ip: Mapped[str] = mapped_column(INET, nullable=False)
    dst_ip: Mapped[str | None] = mapped_column(INET)
    dst_port: Mapped[int | None] = mapped_column(Integer)
    protocol: Mapped[str | None] = mapped_column(String(16))
    user_agent: Mapped[str | None] = mapped_column(String(500))
    country: Mapped[str | None] = mapped_column(String(2))
    raw: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class Alert(UUIDPrimaryKey, Base):
    __tablename__ = "alerts"
    __table_args__ = (
        # Re-running detection over the same data can't create duplicate alerts.
        UniqueConstraint("rule_id", "dedupe_key", name="uq_alerts_rule_dedupe"),
        Index("ix_alerts_status_first_seen", "status", "first_seen"),
    )

    rule_id: Mapped[str] = mapped_column(String(20), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    severity: Mapped[Severity] = mapped_column(Enum(Severity, name="severity"), nullable=False)
    status: Mapped[AlertStatus] = mapped_column(
        Enum(AlertStatus, name="alert_status"), default=AlertStatus.open, nullable=False
    )
    src_ip: Mapped[str | None] = mapped_column(INET, index=True)
    username: Mapped[str | None] = mapped_column(String(128))
    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    event_count: Mapped[int] = mapped_column(Integer, nullable=False)
    details: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    dedupe_key: Mapped[str] = mapped_column(String(300), nullable=False)
    upload_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("log_uploads.id", ondelete="CASCADE"), nullable=False
    )
    incident_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("incidents.id", ondelete="SET NULL"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )

    @property
    def rule_name(self) -> str:
        from app.detection.rules import RULES_BY_ID  # local import avoids a cycle

        rule = RULES_BY_ID.get(self.rule_id)
        return rule.name if rule else self.rule_id

    @property
    def rule_description(self) -> str:
        from app.detection.rules import RULES_BY_ID

        rule = RULES_BY_ID.get(self.rule_id)
        return rule.description if rule else ""


class AlertEvent(Base):
    """Evidence link: which events caused which alert (capped per alert)."""

    __tablename__ = "alert_events"

    alert_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("alerts.id", ondelete="CASCADE"), primary_key=True
    )
    event_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("security_events.id", ondelete="CASCADE"), primary_key=True
    )


class AiAnalysis(UUIDPrimaryKey, Base):
    """AI output, stored apart from verified data and labeled with model + prompt version."""

    __tablename__ = "ai_analyses"
    __table_args__ = (
        UniqueConstraint(
            "target_type",
            "target_id",
            "kind",
            "input_hash",
            "prompt_version",
            name="uq_ai_analyses_cache_key",
        ),
        Index("ix_ai_analyses_target", "target_type", "target_id"),
    )

    target_type: Mapped[str] = mapped_column(String(20), nullable=False)
    target_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    kind: Mapped[str] = mapped_column(String(30), nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(30), nullable=False)
    input_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    output: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    tokens_in: Mapped[int | None] = mapped_column(Integer)
    tokens_out: Mapped[int | None] = mapped_column(Integer)
    requested_by_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), index=True, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True, nullable=False
    )

    requested_by: Mapped[User] = relationship(lazy="joined")
