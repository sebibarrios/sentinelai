from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from app.models.enums import Severity


@dataclass(frozen=True)
class Event:
    """Minimal view of a normalized event that rules operate on.

    `ref` identifies the event in the caller's world (e.g. its index in the upload),
    so alerts can link back to the exact rows that triggered them.
    """

    ref: int
    occurred_at: datetime
    category: str
    outcome: str
    src_ip: str
    username: str | None = None
    dst_ip: str | None = None
    dst_port: int | None = None
    country: str | None = None


@dataclass
class AlertCandidate:
    rule_id: str
    title: str
    severity: Severity
    events: list[Event]
    details: dict[str, Any] = field(default_factory=dict)
    src_ip: str | None = None
    username: str | None = None
    dedupe_key: str = ""

    @property
    def first_seen(self) -> datetime:
        return min(e.occurred_at for e in self.events)

    @property
    def last_seen(self) -> datetime:
        return max(e.occurred_at for e in self.events)


@dataclass(frozen=True)
class Rule:
    id: str
    name: str
    description: str
    severity: Severity
    detect: Callable[[Sequence[Event]], list[AlertCandidate]]


def group_by(events: Iterable[Event], key: Callable[[Event], Any]) -> dict[Any, list[Event]]:
    groups: dict[Any, list[Event]] = {}
    for e in events:
        k = key(e)
        if k is not None:
            groups.setdefault(k, []).append(e)
    return groups


def bursts(
    events: Sequence[Event],
    window: timedelta,
    is_dense: Callable[[Sequence[Event]], bool],
) -> list[list[Event]]:
    """Find maximal bursts in time-sorted events.

    A sliding window [left, right] moves across the events. Whenever the events in
    the window satisfy `is_dense`, they join the current burst; overlapping dense
    windows are merged, so one sustained attack produces one alert, not dozens.
    Runs in O(n * cost(is_dense)).
    """
    result: list[list[Event]] = []
    current: list[Event] = []
    current_refs: set[int] = set()
    left = 0
    for right in range(len(events)):
        while events[right].occurred_at - events[left].occurred_at > window:
            left += 1
        win = events[left : right + 1]
        if is_dense(win):
            if (
                current
                and win[0].ref not in current_refs
                and win[0].occurred_at > current[-1].occurred_at
            ):
                result.append(current)
                current, current_refs = [], set()
            for e in win:
                if e.ref not in current_refs:
                    current.append(e)
                    current_refs.add(e.ref)
    if current:
        result.append(current)
    return result
