"""Output contracts for AI analyses.

The model is asked for exactly these shapes (OpenAI structured outputs), and the
result is validated again with Pydantic before it's stored or shown.
"""

from typing import Literal

from pydantic import BaseModel, Field

SeverityLevel = Literal["low", "medium", "high", "critical"]
Confidence = Literal["low", "medium", "high"]


class InvestigationStep(BaseModel):
    step: str = Field(description="A concrete action an analyst can take")
    rationale: str = Field(description="Why this step matters for this alert")


class AlertExplanation(BaseModel):
    summary: str = Field(description="2-4 sentence plain-English summary")
    explanation: str = Field(description="What the evidence shows and why it is suspicious")
    likely_tactics: list[str] = Field(description="Attacker techniques consistent with evidence")
    investigation_steps: list[InvestigationStep] = Field(description="3-6 ordered next steps")
    recommended_severity: SeverityLevel
    confidence: Confidence
    caveats: list[str] = Field(description="What the evidence does not establish")


class TimelineEntry(BaseModel):
    time: str = Field(description="UTC timestamp or range taken from the input")
    event: str


class Indicator(BaseModel):
    type: Literal["ip", "username", "port", "other"]
    value: str
    context: str


class IncidentReport(BaseModel):
    executive_summary: str = Field(description="3-5 sentences for a non-technical reader")
    timeline: list[TimelineEntry]
    affected_accounts: list[str]
    indicators: list[Indicator] = Field(description="Only values that appear in the input")
    impact_assessment: str
    containment_steps: list[str]
    recommendations: list[str]
    open_questions: list[str] = Field(description="What still needs to be verified")
    caveats: list[str]
