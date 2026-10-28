"""rate limits and session revocation

Revision ID: 462f2d79dbf0
Revises: ef4b1596f2d8
Create Date: 2026-10-28 16:53:57.940921

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "462f2d79dbf0"
down_revision: str | Sequence[str] | None = "ef4b1596f2d8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "rate_limit_hits",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("scope", sa.String(length=40), nullable=False),
        sa.Column("key", sa.String(length=320), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_rate_limit_hits")),
    )
    op.create_index(
        op.f("ix_rate_limit_hits_created_at"), "rate_limit_hits", ["created_at"], unique=False
    )
    op.create_index(
        "ix_rate_limit_hits_scope_key_at",
        "rate_limit_hits",
        ["scope", "key", "created_at"],
        unique=False,
    )
    op.add_column(
        "users", sa.Column("session_version", sa.Integer(), server_default="0", nullable=False)
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("users", "session_version")
    op.drop_index("ix_rate_limit_hits_scope_key_at", table_name="rate_limit_hits")
    op.drop_index(op.f("ix_rate_limit_hits_created_at"), table_name="rate_limit_hits")
    op.drop_table("rate_limit_hits")
