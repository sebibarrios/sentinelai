"""AI analysis service: cache by evidence hash, rate-limit per user, ground the output.

Flow for every request:
1. Build the model input from verified data only (alert facts + evidence events).
2. Hash it (with the prompt version and model). Same input -> return the stored
   analysis instead of paying for another call.
3. Enforce a per-user hourly limit on *new* model calls.
4. Call the model with a strict output schema, then drop any indicator the model
   produced that doesn't literally appear in the input (grounding check).
"""

import hashlib
import json
import re
from datetime import timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.ai import prompts
from app.ai.client import AIClient, AIUnavailable
from app.ai.schemas import AlertExplanation, IncidentReport
from app.core.config import get_settings
from app.core.errors import ServiceUnavailable, TooManyRequests
from app.db.base import utcnow
from app.models import AiAnalysis, Alert, Incident, User
from app.models.enums import AiKind, AiTarget
from app.services import rate_limit
from app.services.alerts import evidence_for


class AIServiceError(ServiceUnavailable):
    status_code = 502
    code = "ai_unavailable"


def _require(client: AIClient | None) -> AIClient:
    if client is None:
        raise ServiceUnavailable("AI analysis is turned off on this server.")
    return client


def _hash(data: dict[str, Any], prompt_version: str, model: str) -> str:
    canonical = json.dumps(data, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(f"{prompt_version}|{model}|{canonical}".encode()).hexdigest()


def _cached(db: Session, target_type: str, target_id, kind: str, input_hash: str, version: str):
    return db.scalar(
        select(AiAnalysis).where(
            AiAnalysis.target_type == target_type,
            AiAnalysis.target_id == target_id,
            AiAnalysis.kind == kind,
            AiAnalysis.input_hash == input_hash,
            AiAnalysis.prompt_version == version,
        )
    )


def _check_rate_limit(db: Session, user: User) -> None:
    limit = get_settings().ai_requests_per_hour
    recent = (
        db.scalar(
            select(func.count())
            .select_from(AiAnalysis)
            .where(
                AiAnalysis.requested_by_id == user.id,
                AiAnalysis.created_at >= utcnow() - timedelta(hours=1),
            )
        )
        or 0
    )
    if recent >= limit:
        raise TooManyRequests(f"AI request limit reached ({limit} per hour). Try again later.")
    # Then the site-wide daily budget, counted atomically before the (billable) call so
    # simultaneous requests can't overshoot it. Failed calls count too: they may still
    # have used tokens.
    rate_limit.reserve(db, rate_limit.ai_requests_site_wide(), "all")
    db.commit()


def _ground_indicators(report: IncidentReport, data: dict[str, Any]) -> tuple[IncidentReport, int]:
    """Remove indicators whose value doesn't appear anywhere in the input data."""
    haystack = json.dumps(data, default=str).lower()
    kept = []
    for ind in report.indicators:
        value = ind.value.strip().lower()
        if value and (re.search(rf"(?<![\w.]){re.escape(value)}(?![\w.])", haystack) is not None):
            kept.append(ind)
    removed = len(report.indicators) - len(kept)
    return report.model_copy(update={"indicators": kept}), removed


def _store(
    db: Session,
    *,
    target_type: AiTarget,
    target_id,
    kind: AiKind,
    version: str,
    input_hash: str,
    output: dict[str, Any],
    completion,
    user: User,
) -> AiAnalysis:
    analysis = AiAnalysis(
        target_type=target_type.value,
        target_id=target_id,
        kind=kind.value,
        model=completion.model,
        prompt_version=version,
        input_hash=input_hash,
        output=output,
        tokens_in=completion.tokens_in,
        tokens_out=completion.tokens_out,
        requested_by_id=user.id,
    )
    db.add(analysis)
    try:
        db.commit()
    except IntegrityError:
        # Two identical requests raced; the other one stored first. Return its result.
        db.rollback()
        existing = _cached(db, target_type.value, target_id, kind.value, input_hash, version)
        if existing is None:
            raise
        return existing
    db.refresh(analysis)
    return analysis


def explain_alert(
    db: Session, alert: Alert, user: User, client: AIClient | None
) -> tuple[AiAnalysis, bool]:
    client = _require(client)
    data = prompts.alert_input(alert, evidence_for(db, alert))
    version = prompts.ALERT_PROMPT_VERSION
    input_hash = _hash(data, version, client.model)

    if hit := _cached(db, "alert", alert.id, AiKind.alert_explanation.value, input_hash, version):
        return hit, True

    _check_rate_limit(db, user)
    try:
        completion = client.complete(
            instructions=prompts.ALERT_INSTRUCTIONS,
            user=prompts.render_user_message(data),
            schema=AlertExplanation,
        )
    except AIUnavailable as exc:
        raise AIServiceError(str(exc)) from exc

    analysis = _store(
        db,
        target_type=AiTarget.alert,
        target_id=alert.id,
        kind=AiKind.alert_explanation,
        version=version,
        input_hash=input_hash,
        output=completion.parsed.model_dump(),
        completion=completion,
        user=user,
    )
    return analysis, False


def incident_report(
    db: Session, incident: Incident, user: User, client: AIClient | None
) -> tuple[AiAnalysis, bool]:
    client = _require(client)
    alerts = list(
        db.scalars(select(Alert).where(Alert.incident_id == incident.id).order_by(Alert.first_seen))
    )
    data = prompts.incident_input(incident, alerts, {a.id: evidence_for(db, a) for a in alerts})
    version = prompts.INCIDENT_PROMPT_VERSION
    input_hash = _hash(data, version, client.model)

    if hit := _cached(
        db, "incident", incident.id, AiKind.incident_report.value, input_hash, version
    ):
        return hit, True

    _check_rate_limit(db, user)
    try:
        completion = client.complete(
            instructions=prompts.INCIDENT_INSTRUCTIONS,
            user=prompts.render_user_message(data),
            schema=IncidentReport,
        )
    except AIUnavailable as exc:
        raise AIServiceError(str(exc)) from exc

    report, removed = _ground_indicators(completion.parsed, data)
    output = report.model_dump()
    output["ungrounded_indicators_removed"] = removed

    analysis = _store(
        db,
        target_type=AiTarget.incident,
        target_id=incident.id,
        kind=AiKind.incident_report,
        version=version,
        input_hash=input_hash,
        output=output,
        completion=completion,
        user=user,
    )
    return analysis, False
