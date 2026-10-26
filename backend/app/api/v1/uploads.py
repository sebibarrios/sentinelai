import uuid

from fastapi import APIRouter, Depends, File, Query, Request, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import Analyst, Viewer
from app.core.config import get_settings
from app.core.errors import NotFound, PayloadTooLarge
from app.db.session import get_db
from app.models import LogUpload, User
from app.schemas.common import Page, PageParams
from app.schemas.security import UploadOut
from app.services.uploads import ingest_upload

router = APIRouter(prefix="/uploads", tags=["uploads"])

CHUNK = 64 * 1024


async def _read_limited(file: UploadFile, limit: int) -> bytes:
    """Read the upload in chunks and stop as soon as it exceeds the limit."""
    data = bytearray()
    while chunk := await file.read(CHUNK):
        data.extend(chunk)
        if len(data) > limit:
            raise PayloadTooLarge(f"File is larger than {limit // (1024 * 1024)} MB.")
    return bytes(data)


@router.post("", response_model=UploadOut, status_code=status.HTTP_201_CREATED)
async def upload_log(
    request: Request,
    file: UploadFile = File(..., description="CSV, JSON array, or NDJSON security log"),
    user: User = Analyst,
    db: Session = Depends(get_db),
) -> LogUpload:
    settings = get_settings()
    limit = settings.max_upload_mb * 1024 * 1024
    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > limit + 64 * 1024:
        raise PayloadTooLarge(f"File is larger than {settings.max_upload_mb} MB.")
    content = await _read_limited(file, limit)
    return ingest_upload(
        db,
        filename=file.filename or "upload",
        content=content,
        user=user,
        max_rows=settings.max_upload_rows,
    )


@router.get("", response_model=Page[UploadOut])
def list_uploads(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    _: User = Viewer,
    db: Session = Depends(get_db),
) -> dict:
    params = PageParams(page=page, page_size=page_size)
    total = db.scalar(select(func.count()).select_from(LogUpload)) or 0
    items = db.scalars(
        select(LogUpload)
        .order_by(LogUpload.created_at.desc())
        .offset(params.offset)
        .limit(params.page_size)
    ).all()
    return {"items": items, "page": page, "page_size": page_size, "total": total}


@router.get("/{upload_id}", response_model=UploadOut)
def get_upload(upload_id: uuid.UUID, _: User = Viewer, db: Session = Depends(get_db)) -> LogUpload:
    upload = db.get(LogUpload, upload_id)
    if upload is None:
        raise NotFound("Upload not found")
    return upload
