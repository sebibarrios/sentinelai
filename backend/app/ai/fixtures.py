"""Deterministic offline AI client for end-to-end tests and keyless demos.

Enabled with AI_OFFLINE_FIXTURES=true; refused in production (see config). It builds
its answer from the real input data, so the UI shows realistic, alert-specific text,
and it labels itself clearly as a fixture so it's never mistaken for model output.

The incident report deliberately includes one indicator that is NOT in the input
(192.0.2.254), so tests can prove the grounding check removes invented values.
"""

import json
import re

from app.ai.client import Completion
from app.ai.schemas import AlertExplanation, IncidentReport

FIXTURE_MODEL = "offline-fixture (not a real model)"
INVENTED_INDICATOR = "192.0.2.254"


def _data(user_message: str) -> dict:
    match = re.search(r"<data>\n(.*)\n</data>", user_message, re.S)
    return json.loads(match.group(1)) if match else {}


class FixtureAIClient:
    model = FIXTURE_MODEL

    def complete(self, *, instructions: str, user: str, schema):
        data = _data(user)
        if schema is AlertExplanation:
            parsed = self._explain(data)
        elif schema is IncidentReport:
            parsed = self._report(data)
        else:  # pragma: no cover - only two schemas exist
            raise ValueError(f"No fixture for {schema.__name__}")
        return Completion(parsed=parsed, model=self.model, tokens_in=0, tokens_out=0)

    @staticmethod
    def _explain(data: dict) -> AlertExplanation:
        alert = data.get("alert", {})
        who = alert.get("username") or "the affected host"
        src = alert.get("src_ip") or "the source"
        return AlertExplanation(
            summary=f"[Offline fixture] {alert.get('title', 'Alert')}: "
            f"{alert.get('event_count', 0)} matching events from {src}.",
            explanation=f"Rule {alert.get('rule_id')} ({alert.get('rule_name')}) matched "
            f"activity involving {who}. This text is generated without a model.",
            likely_tactics=[str(alert.get("rule_name", "Unknown"))],
            investigation_steps=[
                {
                    "step": f"Review all recent activity from {src}",
                    "rationale": "Establish whether the source has other suspicious events.",
                },
                {
                    "step": f"Confirm with the owner of {who} whether the activity was expected",
                    "rationale": "Rules any legitimate explanation in or out.",
                },
            ],
            recommended_severity=alert.get("severity", "medium"),
            confidence="low",
            caveats=["Offline fixture output: no language model was used."],
        )

    @staticmethod
    def _report(data: dict) -> IncidentReport:
        incident = data.get("incident", {})
        alerts = data.get("linked_alerts", [])
        ips = sorted({a["src_ip"] for a in alerts if a.get("src_ip")})
        users = sorted({a["username"] for a in alerts if a.get("username")})
        indicators = [{"type": "ip", "value": ip, "context": "alert source"} for ip in ips]
        indicators += [
            {"type": "username", "value": u, "context": "account in alerts"} for u in users
        ]
        indicators.append(
            {
                "type": "ip",
                "value": INVENTED_INDICATOR,
                "context": "not in the data (grounding test)",
            }
        )
        return IncidentReport(
            executive_summary=f"[Offline fixture] {incident.get('reference')}: "
            f"{incident.get('title')}. {len(alerts)} linked alert(s).",
            timeline=[
                {"time": a.get("first_seen", ""), "event": a.get("title", "")} for a in alerts
            ],
            affected_accounts=users,
            indicators=indicators,
            impact_assessment="Not assessed: offline fixture output.",
            containment_steps=[f"Block {ip} pending review" for ip in ips] or ["Review the alerts"],
            recommendations=["Review with a real model or analyst before acting"],
            open_questions=["What happened after the last recorded event?"],
            caveats=["Offline fixture output: no language model was used."],
        )
