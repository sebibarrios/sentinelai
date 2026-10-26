"""Upload pipeline: parse -> store events -> run detection -> store alerts + evidence.

Everything for one upload happens in a single transaction, so a failure part-way
leaves no half-imported data behind.
"""

import hashlib
import time

from sqlalchemy import insert, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.core.errors import AppError, Conflict
from app.db.base import utcnow
from app.detection.base import Event
from app.detection.engine import run_rules
from app.ingest.parser import ParseError, parse_log
from app.models import Alert, AlertEvent, LogUpload, SecurityEvent, User
from app.models.enums import UploadStatus

MAX_EVIDENCE_PER_ALERT = 200
INSERT_BATCH = 2_000


class UploadRejected(AppError):
    status_code = 422
    code = "upload_rejected"


def ingest_upload(
    db: Session, *, filename: str, content: bytes, user: User, max_rows: int
) -> LogUpload:
    started = time.perf_counter()
    sha256 = hashlib.sha256(content).hexdigest()

    existing = db.scalar(
        select(LogUpload).where(
            LogUpload.sha256 == sha256, LogUpload.status == UploadStatus.completed
        )
    )
    if existing:
        raise Conflict(
            "This exact file was already uploaded.",
            details={"upload_id": str(existing.id), "uploaded_at": existing.created_at.isoformat()},
        )

    try:
        parsed = parse_log(filename, content, max_rows=max_rows)
    except ParseError as exc:
        raise UploadRejected(str(exc)) from exc
    if not parsed.rows:
        raise UploadRejected(
            "No valid rows found in the file.",
            details=[
                {"field": f"line {s['line']}", "message": s["reason"]}
                for s in parsed.rejection_samples
            ],
        )

    upload = LogUpload(
        original_filename=filename[-255:],
        format=parsed.format,
        size_bytes=len(content),
        sha256=sha256,
        status=UploadStatus.processing,
        rows_total=parsed.total,
        rows_parsed=len(parsed.rows),
        rows_rejected=parsed.rejected_count,
        rejection_samples=parsed.rejection_samples,
        uploaded_by_id=user.id,
    )
    db.add(upload)
    db.flush()

    # 1) Bulk-insert events, keeping each row's database id in upload order.
    event_ids: list[int] = []
    rows = [
        {
            "upload_id": upload.id,
            "occurred_at": r.event.timestamp,
            "category": r.event.category,
            "action": r.event.action,
            "outcome": r.event.outcome,
            "username": r.event.username,
            "src_ip": r.event.src_ip,
            "dst_ip": r.event.dst_ip,
            "dst_port": r.event.dst_port,
            "protocol": r.event.protocol,
            "user_agent": r.event.user_agent,
            "country": r.event.country,
            "raw": r.raw,
        }
        for r in parsed.rows
    ]
    for i in range(0, len(rows), INSERT_BATCH):
        batch = rows[i : i + INSERT_BATCH]
        result = db.execute(
            insert(SecurityEvent).returning(SecurityEvent.id, sort_by_parameter_order=True), batch
        )
        event_ids.extend(result.scalars().all())

    # 2) Detection runs on lightweight Event views; `ref` is the row index.
    events = [
        Event(
            ref=i,
            occurred_at=r.event.timestamp,
            category=r.event.category,
            outcome=r.event.outcome,
            src_ip=r.event.src_ip,
            username=r.event.username,
            dst_ip=r.event.dst_ip,
            dst_port=r.event.dst_port,
            country=r.event.country,
        )
        for i, r in enumerate(parsed.rows)
    ]
    candidates = run_rules(events)

    # 3) Store alerts; ON CONFLICT skips alerts already found in an earlier upload.
    created = 0
    for c in candidates:
        alert_id = db.scalar(
            pg_insert(Alert)
            .values(
                rule_id=c.rule_id,
                title=c.title[:300],
                severity=c.severity,
                src_ip=c.src_ip,
                username=c.username,
                first_seen=c.first_seen,
                last_seen=c.last_seen,
                event_count=len(c.events),
                details=c.details,
                dedupe_key=c.dedupe_key[:300],
                upload_id=upload.id,
            )
            .on_conflict_do_nothing(constraint="uq_alerts_rule_dedupe")
            .returning(Alert.id)
        )
        if alert_id is None:
            continue
        created += 1
        evidence = sorted(c.events, key=lambda e: e.occurred_at)[:MAX_EVIDENCE_PER_ALERT]
        db.execute(
            insert(AlertEvent),
            [{"alert_id": alert_id, "event_id": event_ids[e.ref]} for e in evidence],
        )

    upload.alerts_created = created
    upload.status = UploadStatus.completed
    upload.completed_at = utcnow()
    upload.processing_ms = int((time.perf_counter() - started) * 1000)
    db.commit()
    db.refresh(upload)
    return upload
