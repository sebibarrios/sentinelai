import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Identity, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, Timestamps, UUIDPrimaryKey, utcnow
from app.models.enums import HistoryAction, IncidentStatus, Severity
from app.models.user import User


class Incident(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "incidents"
    __table_args__ = (Index("ix_incidents_status_created_at", "status", "created_at"),)

    # Sequential number for human-friendly references like INC-0042.
    number: Mapped[int] = mapped_column(Integer, Identity(), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    severity: Mapped[Severity] = mapped_column(Enum(Severity, name="severity"), nullable=False)
    status: Mapped[IncidentStatus] = mapped_column(
        Enum(IncidentStatus, name="incident_status"), default=IncidentStatus.open, nullable=False
    )
    assignee_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    created_by_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    assignee: Mapped[User | None] = relationship(foreign_keys=[assignee_id], lazy="joined")
    created_by: Mapped[User] = relationship(foreign_keys=[created_by_id], lazy="joined")
    notes: Mapped[list["IncidentNote"]] = relationship(
        back_populates="incident", order_by="IncidentNote.created_at", cascade="all, delete-orphan"
    )

    @property
    def reference(self) -> str:
        return f"INC-{self.number:04d}"


class IncidentNote(UUIDPrimaryKey, Base):
    __tablename__ = "incident_notes"

    incident_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("incidents.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    author_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    incident: Mapped[Incident] = relationship(back_populates="notes")
    author: Mapped[User] = relationship(lazy="joined")


class IncidentHistory(Base):
    """Append-only audit trail. Written by the service layer on every change."""

    __tablename__ = "incident_history"

    id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    incident_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("incidents.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    actor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    action: Mapped[HistoryAction] = mapped_column(
        Enum(HistoryAction, name="history_action"), nullable=False
    )
    field: Mapped[str | None] = mapped_column(String(50))
    old_value: Mapped[str | None] = mapped_column(Text)
    new_value: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    actor: Mapped[User] = relationship(lazy="joined")
