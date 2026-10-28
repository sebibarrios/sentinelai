from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Identity, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, utcnow


class RateLimitHit(Base):
    """One counted event (e.g. a failed login) for sliding-window rate limits.

    Stored in PostgreSQL rather than process memory so limits hold across restarts
    and across multiple API instances.
    """

    __tablename__ = "rate_limit_hits"
    __table_args__ = (Index("ix_rate_limit_hits_scope_key_at", "scope", "key", "created_at"),)

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    scope: Mapped[str] = mapped_column(String(40), nullable=False)
    key: Mapped[str] = mapped_column(String(320), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True, nullable=False
    )
