import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.ai.client import AIClient
from app.ai.provider import get_ai_client
from app.api.deps import Analyst, Viewer
from app.core.config import get_settings
from app.db.session import get_db
from app.models import User
from app.schemas.security import AiAnalysisOut
from app.services import ai as svc
from app.services.alerts import get_alert, latest_analysis
from app.services.incidents import get_incident

router = APIRouter(prefix="/ai", tags=["ai"])


class AiResult(AiAnalysisOut):
    cached: bool


@router.get("/status")
def ai_status(_: User = Viewer) -> dict:
    """Lets the UI show whether AI features are available, without exposing the key."""
    settings = get_settings()
    if settings.ai_offline_fixtures:
        from app.ai.fixtures import FIXTURE_MODEL

        return {"enabled": True, "model": FIXTURE_MODEL}
    return {"enabled": bool(settings.openai_api_key), "model": settings.openai_model}


@router.post("/alerts/{alert_id}/explain", response_model=AiResult)
def explain_alert(
    alert_id: uuid.UUID,
    user: User = Analyst,
    db: Session = Depends(get_db),
    client: AIClient | None = Depends(get_ai_client),
) -> dict:
    analysis, cached = svc.explain_alert(db, get_alert(db, alert_id), user, client)
    return {**AiAnalysisOut.model_validate(analysis).model_dump(), "cached": cached}


@router.post("/incidents/{incident_id}/report", response_model=AiResult)
def incident_report(
    incident_id: uuid.UUID,
    user: User = Analyst,
    db: Session = Depends(get_db),
    client: AIClient | None = Depends(get_ai_client),
) -> dict:
    analysis, cached = svc.incident_report(db, get_incident(db, incident_id), user, client)
    return {**AiAnalysisOut.model_validate(analysis).model_dump(), "cached": cached}


@router.get("/incidents/{incident_id}/report", response_model=AiAnalysisOut | None)
def latest_incident_report(incident_id: uuid.UUID, _: User = Viewer, db: Session = Depends(get_db)):
    get_incident(db, incident_id)  # 404 if missing
    return latest_analysis(db, "incident", incident_id)
