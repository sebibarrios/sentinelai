from collections.abc import Iterable

from app.detection.base import AlertCandidate, Event
from app.detection.rules import RULES


def run_rules(events: Iterable[Event]) -> list[AlertCandidate]:
    """Run every rule over the events (sorted by time first) and return all candidates."""
    ordered = sorted(events, key=lambda e: (e.occurred_at, e.ref))
    candidates: list[AlertCandidate] = []
    for rule in RULES:
        candidates.extend(rule.detect(ordered))
    return candidates
