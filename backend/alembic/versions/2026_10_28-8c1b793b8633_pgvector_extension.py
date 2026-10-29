"""pgvector extension

Revision ID: 8c1b793b8633
Revises: 462f2d79dbf0
Create Date: 2026-10-28 22:06:46.009768

Enables vector similarity search for the v2 knowledge base. On managed databases
(Neon, RDS) the database owner may create it; on a self-hosted server it needs a
superuser once: CREATE EXTENSION vector;
"""

from collections.abc import Sequence

from alembic import op

revision: str = "8c1b793b8633"
down_revision: str | Sequence[str] | None = "462f2d79dbf0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")


def downgrade() -> None:
    # The extension is left in place: it's database infrastructure, not app data, and
    # dropping it can require superuser rights the app role doesn't have.
    pass
