import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from pydantic import IPvAnyAddress
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import Viewer
from app.db.session import get_db
from app.models import SecurityEvent, User
from app.models.enums import EventCategory, EventOutcome
from app.schemas.common import Page, PageParams
from app.schemas.security import EventOut

router = APIRouter(prefix="/events", tags=["events"])


@router.get("", response_model=Page[EventOut])
def list_events(
    category: EventCategory | None = None,
    outcome: EventOutcome | None = None,
    username: str | None = Query(None, max_length=128),
    src_ip: IPvAnyAddress | None = None,
    upload_id: uuid.UUID | None = None,
    since: datetime | None = Query(None, alias="from"),
    until: datetime | None = Query(None, alias="to"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    _: User = Viewer,
    db: Session = Depends(get_db),
) -> dict:
    stmt = select(SecurityEvent)
    if category:
        stmt = stmt.where(SecurityEvent.category == category)
    if outcome:
        stmt = stmt.where(SecurityEvent.outcome == outcome)
    if username:
        stmt = stmt.where(SecurityEvent.username == username)
    if src_ip:
        stmt = stmt.where(SecurityEvent.src_ip == str(src_ip))
    if upload_id:
        stmt = stmt.where(SecurityEvent.upload_id == upload_id)
    if since:
        stmt = stmt.where(SecurityEvent.occurred_at >= since)
    if until:
        stmt = stmt.where(SecurityEvent.occurred_at <= until)

    params = PageParams(page=page, page_size=page_size)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    items = db.scalars(
        stmt.order_by(SecurityEvent.occurred_at.desc(), SecurityEvent.id.desc())
        .offset(params.offset)
        .limit(params.page_size)
    ).all()
    return {"items": items, "page": page, "page_size": page_size, "total": total}
