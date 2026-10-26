"""log uploads, events, alerts, ai analyses

Revision ID: ef4b1596f2d8
Revises: 9c6d45e90ce1
Create Date: 2026-10-25 21:45:01.593840

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "ef4b1596f2d8"
down_revision: str | Sequence[str] | None = "9c6d45e90ce1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "ai_analyses",
        sa.Column("target_type", sa.String(length=20), nullable=False),
        sa.Column("target_id", sa.UUID(), nullable=False),
        sa.Column("kind", sa.String(length=30), nullable=False),
        sa.Column("model", sa.String(length=100), nullable=False),
        sa.Column("prompt_version", sa.String(length=30), nullable=False),
        sa.Column("input_hash", sa.String(length=64), nullable=False),
        sa.Column("output", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("tokens_in", sa.Integer(), nullable=True),
        sa.Column("tokens_out", sa.Integer(), nullable=True),
        sa.Column("requested_by_id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(
            ["requested_by_id"], ["users.id"], name=op.f("fk_ai_analyses_requested_by_id_users")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ai_analyses")),
        sa.UniqueConstraint(
            "target_type",
            "target_id",
            "kind",
            "input_hash",
            "prompt_version",
            name="uq_ai_analyses_cache_key",
        ),
    )
    op.create_index(op.f("ix_ai_analyses_created_at"), "ai_analyses", ["created_at"], unique=False)
    op.create_index(
        op.f("ix_ai_analyses_requested_by_id"), "ai_analyses", ["requested_by_id"], unique=False
    )
    op.create_index(
        "ix_ai_analyses_target", "ai_analyses", ["target_type", "target_id"], unique=False
    )
    op.create_table(
        "log_uploads",
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("format", sa.String(length=10), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column(
            "status",
            sa.Enum("processing", "completed", "failed", name="upload_status"),
            nullable=False,
        ),
        sa.Column("rows_total", sa.Integer(), nullable=False),
        sa.Column("rows_parsed", sa.Integer(), nullable=False),
        sa.Column("rows_rejected", sa.Integer(), nullable=False),
        sa.Column("alerts_created", sa.Integer(), nullable=False),
        sa.Column("rejection_samples", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("processing_ms", sa.Integer(), nullable=True),
        sa.Column("uploaded_by_id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(
            ["uploaded_by_id"], ["users.id"], name=op.f("fk_log_uploads_uploaded_by_id_users")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_log_uploads")),
    )
    op.create_index(op.f("ix_log_uploads_created_at"), "log_uploads", ["created_at"], unique=False)
    op.create_index(op.f("ix_log_uploads_sha256"), "log_uploads", ["sha256"], unique=False)
    op.create_table(
        "alerts",
        sa.Column("rule_id", sa.String(length=20), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column(
            "severity",
            postgresql.ENUM(
                "low", "medium", "high", "critical", name="severity", create_type=False
            ),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum("open", "acknowledged", "dismissed", "escalated", name="alert_status"),
            nullable=False,
        ),
        sa.Column("src_ip", postgresql.INET(), nullable=True),
        sa.Column("username", sa.String(length=128), nullable=True),
        sa.Column("first_seen", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen", sa.DateTime(timezone=True), nullable=False),
        sa.Column("event_count", sa.Integer(), nullable=False),
        sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("dedupe_key", sa.String(length=300), nullable=False),
        sa.Column("upload_id", sa.UUID(), nullable=False),
        sa.Column("incident_id", sa.UUID(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(
            ["incident_id"],
            ["incidents.id"],
            name=op.f("fk_alerts_incident_id_incidents"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["upload_id"],
            ["log_uploads.id"],
            name=op.f("fk_alerts_upload_id_log_uploads"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_alerts")),
        sa.UniqueConstraint("rule_id", "dedupe_key", name="uq_alerts_rule_dedupe"),
    )
    op.create_index(op.f("ix_alerts_incident_id"), "alerts", ["incident_id"], unique=False)
    op.create_index(op.f("ix_alerts_rule_id"), "alerts", ["rule_id"], unique=False)
    op.create_index(op.f("ix_alerts_src_ip"), "alerts", ["src_ip"], unique=False)
    op.create_index("ix_alerts_status_first_seen", "alerts", ["status", "first_seen"], unique=False)
    op.create_table(
        "security_events",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("upload_id", sa.UUID(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("category", sa.Enum("auth", "network", name="event_category"), nullable=False),
        sa.Column("action", sa.String(length=50), nullable=False),
        sa.Column(
            "outcome",
            sa.Enum("success", "failure", "allowed", "denied", name="event_outcome"),
            nullable=False,
        ),
        sa.Column("username", sa.String(length=128), nullable=True),
        sa.Column("src_ip", postgresql.INET(), nullable=False),
        sa.Column("dst_ip", postgresql.INET(), nullable=True),
        sa.Column("dst_port", sa.Integer(), nullable=True),
        sa.Column("protocol", sa.String(length=16), nullable=True),
        sa.Column("user_agent", sa.String(length=500), nullable=True),
        sa.Column("country", sa.String(length=2), nullable=True),
        sa.Column("raw", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.CheckConstraint(
            "dst_port BETWEEN 0 AND 65535", name=op.f("ck_security_events_dst_port_range")
        ),
        sa.ForeignKeyConstraint(
            ["upload_id"],
            ["log_uploads.id"],
            name=op.f("fk_security_events_upload_id_log_uploads"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_security_events")),
    )
    op.create_index(
        op.f("ix_security_events_occurred_at"), "security_events", ["occurred_at"], unique=False
    )
    op.create_index(
        "ix_security_events_src_ip_occurred_at",
        "security_events",
        ["src_ip", "occurred_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_security_events_upload_id"), "security_events", ["upload_id"], unique=False
    )
    op.create_index(
        "ix_security_events_username_occurred_at",
        "security_events",
        ["username", "occurred_at"],
        unique=False,
    )
    op.create_table(
        "alert_events",
        sa.Column("alert_id", sa.UUID(), nullable=False),
        sa.Column("event_id", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(
            ["alert_id"],
            ["alerts.id"],
            name=op.f("fk_alert_events_alert_id_alerts"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["event_id"],
            ["security_events.id"],
            name=op.f("fk_alert_events_event_id_security_events"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("alert_id", "event_id", name=op.f("pk_alert_events")),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("alert_events")
    op.drop_index("ix_security_events_username_occurred_at", table_name="security_events")
    op.drop_index(op.f("ix_security_events_upload_id"), table_name="security_events")
    op.drop_index("ix_security_events_src_ip_occurred_at", table_name="security_events")
    op.drop_index(op.f("ix_security_events_occurred_at"), table_name="security_events")
    op.drop_table("security_events")
    op.drop_index("ix_alerts_status_first_seen", table_name="alerts")
    op.drop_index(op.f("ix_alerts_src_ip"), table_name="alerts")
    op.drop_index(op.f("ix_alerts_rule_id"), table_name="alerts")
    op.drop_index(op.f("ix_alerts_incident_id"), table_name="alerts")
    op.drop_table("alerts")
    op.drop_index(op.f("ix_log_uploads_sha256"), table_name="log_uploads")
    op.drop_index(op.f("ix_log_uploads_created_at"), table_name="log_uploads")
    op.drop_table("log_uploads")
    op.drop_index("ix_ai_analyses_target", table_name="ai_analyses")
    op.drop_index(op.f("ix_ai_analyses_requested_by_id"), table_name="ai_analyses")
    op.drop_index(op.f("ix_ai_analyses_created_at"), table_name="ai_analyses")
    op.drop_table("ai_analyses")
    for enum in ("alert_status", "event_category", "event_outcome", "upload_status"):
        op.execute(f"DROP TYPE IF EXISTS {enum}")
