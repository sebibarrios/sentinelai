"""users and incidents

Revision ID: 9c6d45e90ce1
Revises:
Create Date: 2026-10-25 20:48:48.967748

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "9c6d45e90ce1"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # Case-insensitive email column type.
    op.execute("CREATE EXTENSION IF NOT EXISTS citext")
    op.create_table(
        "users",
        sa.Column("email", postgresql.CITEXT(), nullable=False),
        sa.Column("password_hash", sa.String(), nullable=False),
        sa.Column("full_name", sa.String(length=120), nullable=False),
        sa.Column("role", sa.Enum("admin", "analyst", "viewer", name="user_role"), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("email", name=op.f("uq_users_email")),
    )
    op.create_table(
        "incidents",
        sa.Column("number", sa.Integer(), sa.Identity(always=False), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column(
            "severity",
            sa.Enum("low", "medium", "high", "critical", name="severity"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "open", "investigating", "contained", "resolved", "closed", name="incident_status"
            ),
            nullable=False,
        ),
        sa.Column("assignee_id", sa.UUID(), nullable=True),
        sa.Column("created_by_id", sa.UUID(), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["assignee_id"],
            ["users.id"],
            name=op.f("fk_incidents_assignee_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_id"], ["users.id"], name=op.f("fk_incidents_created_by_id_users")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_incidents")),
        sa.UniqueConstraint("number", name=op.f("uq_incidents_number")),
    )
    op.create_index(op.f("ix_incidents_assignee_id"), "incidents", ["assignee_id"], unique=False)
    op.create_index("ix_incidents_status_created_at", "incidents", ["status", "created_at"])
    op.create_table(
        "incident_history",
        sa.Column("id", sa.Integer(), sa.Identity(always=False), nullable=False),
        sa.Column("incident_id", sa.UUID(), nullable=False),
        sa.Column("actor_id", sa.UUID(), nullable=False),
        sa.Column(
            "action",
            sa.Enum(
                "created",
                "updated",
                "assigned",
                "status_changed",
                "note_added",
                "alert_linked",
                name="history_action",
            ),
            nullable=False,
        ),
        sa.Column("field", sa.String(length=50), nullable=True),
        sa.Column("old_value", sa.Text(), nullable=True),
        sa.Column("new_value", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["actor_id"], ["users.id"], name=op.f("fk_incident_history_actor_id_users")
        ),
        sa.ForeignKeyConstraint(
            ["incident_id"],
            ["incidents.id"],
            name=op.f("fk_incident_history_incident_id_incidents"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_incident_history")),
    )
    op.create_index(
        op.f("ix_incident_history_incident_id"), "incident_history", ["incident_id"], unique=False
    )
    op.create_table(
        "incident_notes",
        sa.Column("incident_id", sa.UUID(), nullable=False),
        sa.Column("author_id", sa.UUID(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(
            ["author_id"], ["users.id"], name=op.f("fk_incident_notes_author_id_users")
        ),
        sa.ForeignKeyConstraint(
            ["incident_id"],
            ["incidents.id"],
            name=op.f("fk_incident_notes_incident_id_incidents"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_incident_notes")),
    )
    op.create_index(
        op.f("ix_incident_notes_incident_id"), "incident_notes", ["incident_id"], unique=False
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_incident_notes_incident_id"), table_name="incident_notes")
    op.drop_table("incident_notes")
    op.drop_index(op.f("ix_incident_history_incident_id"), table_name="incident_history")
    op.drop_table("incident_history")
    op.drop_index("ix_incidents_status_created_at", table_name="incidents")
    op.drop_index(op.f("ix_incidents_assignee_id"), table_name="incidents")
    op.drop_table("incidents")
    op.drop_table("users")
    for enum in ("history_action", "incident_status", "severity", "user_role"):
        op.execute(f"DROP TYPE IF EXISTS {enum}")
