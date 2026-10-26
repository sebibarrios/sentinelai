"""Detection rules. Each one is a pure function: time-sorted events -> alert candidates.

Thresholds are module constants so tests (and future config) can reason about them.
"""

from collections.abc import Sequence
from datetime import timedelta

from app.detection.base import AlertCandidate, Event, Rule, bursts, group_by
from app.detection.blocklist import KNOWN_BAD_IPS
from app.models.enums import Severity

BRUTE_FORCE_FAILURES = 5
BRUTE_FORCE_WINDOW = timedelta(minutes=10)
SPRAY_USERS = 5
SPRAY_WINDOW = timedelta(minutes=15)
SUCCESS_AFTER_FAILURES = 3
SUCCESS_AFTER_WINDOW = timedelta(minutes=15)
OFF_HOURS_UTC = range(0, 5)  # 00:00-04:59 UTC
SCAN_PORTS = 15
SCAN_WINDOW = timedelta(minutes=5)
DENIED_BURST = 20
DENIED_WINDOW = timedelta(minutes=5)


def _auth(events: Sequence[Event], outcome: str) -> list[Event]:
    return [e for e in events if e.category == "auth" and e.outcome == outcome]


def brute_force(events: Sequence[Event]) -> list[AlertCandidate]:
    alerts = []
    for (user, ip), group in group_by(
        _auth(events, "failure"), lambda e: (e.username, e.src_ip)
    ).items():
        for burst in bursts(group, BRUTE_FORCE_WINDOW, lambda w: len(w) >= BRUTE_FORCE_FAILURES):
            alerts.append(
                AlertCandidate(
                    rule_id="AUTH-001",
                    title=f"Brute force: {len(burst)} failed logins for {user} from {ip}",
                    severity=Severity.high,
                    events=burst,
                    details={"failed_attempts": len(burst)},
                    src_ip=ip,
                    username=user,
                    dedupe_key=f"{user}|{ip}|{burst[0].occurred_at.isoformat()}",
                )
            )
    return alerts


def password_spray(events: Sequence[Event]) -> list[AlertCandidate]:
    alerts = []
    for ip, group in group_by(_auth(events, "failure"), lambda e: e.src_ip).items():
        dense = lambda w: len({e.username for e in w}) >= SPRAY_USERS  # noqa: E731
        for burst in bursts(group, SPRAY_WINDOW, dense):
            users = sorted({e.username for e in burst if e.username})
            alerts.append(
                AlertCandidate(
                    rule_id="AUTH-002",
                    title=f"Password spraying: {ip} tried {len(users)} accounts",
                    severity=Severity.high,
                    events=burst,
                    details={"distinct_usernames": len(users), "usernames": users[:25]},
                    src_ip=ip,
                    dedupe_key=f"{ip}|{burst[0].occurred_at.isoformat()}",
                )
            )
    return alerts


def success_after_failures(events: Sequence[Event]) -> list[AlertCandidate]:
    alerts = []
    failures_by_user = group_by(_auth(events, "failure"), lambda e: e.username)
    for success in _auth(events, "success"):
        prior = [
            f
            for f in failures_by_user.get(success.username, [])
            if timedelta(0) <= success.occurred_at - f.occurred_at <= SUCCESS_AFTER_WINDOW
        ]
        if len(prior) >= SUCCESS_AFTER_FAILURES:
            ips = sorted({f.src_ip for f in prior})
            alerts.append(
                AlertCandidate(
                    rule_id="AUTH-003",
                    title=f"Successful login for {success.username} after {len(prior)} failures",
                    severity=Severity.critical,
                    events=[*prior, success],
                    details={
                        "failures_before_success": len(prior),
                        "success_ip": success.src_ip,
                        "failure_ips": ips,
                    },
                    src_ip=success.src_ip,
                    username=success.username,
                    dedupe_key=f"{success.username}|{success.occurred_at.isoformat()}",
                )
            )
    return alerts


def off_hours_login(events: Sequence[Event]) -> list[AlertCandidate]:
    alerts = []
    off = [e for e in _auth(events, "success") if e.occurred_at.hour in OFF_HOURS_UTC]
    for (user, day), group in group_by(off, lambda e: (e.username, e.occurred_at.date())).items():
        alerts.append(
            AlertCandidate(
                rule_id="AUTH-004",
                title=f"Off-hours login by {user} at {group[0].occurred_at:%H:%M} UTC",
                severity=Severity.low,
                events=group,
                details={"logins": len(group), "first_login_utc": f"{group[0].occurred_at:%H:%M}"},
                src_ip=group[0].src_ip,
                username=user,
                dedupe_key=f"{user}|{day.isoformat()}",
            )
        )
    return alerts


def new_source_ip(events: Sequence[Event]) -> list[AlertCandidate]:
    """A successful login from an IP the user hasn't logged in from before (in this data)."""
    alerts = []
    for user, logins in group_by(_auth(events, "success"), lambda e: e.username).items():
        seen = {logins[0].src_ip}  # first login is the baseline
        for login in logins[1:]:
            if login.src_ip not in seen:
                alerts.append(
                    AlertCandidate(
                        rule_id="AUTH-005",
                        title=f"New source IP for {user}: {login.src_ip}",
                        severity=Severity.medium,
                        events=[login],
                        details={"known_ips": sorted(seen), "new_ip": login.src_ip},
                        src_ip=login.src_ip,
                        username=user,
                        dedupe_key=f"{user}|{login.src_ip}",
                    )
                )
                seen.add(login.src_ip)
    return alerts


def port_scan(events: Sequence[Event]) -> list[AlertCandidate]:
    alerts = []
    network = [e for e in events if e.category == "network" and e.dst_port is not None]
    for (src, dst), group in group_by(network, lambda e: (e.src_ip, e.dst_ip)).items():
        dense = lambda w: len({e.dst_port for e in w}) >= SCAN_PORTS  # noqa: E731
        for burst in bursts(group, SCAN_WINDOW, dense):
            ports = sorted({e.dst_port for e in burst if e.dst_port is not None})
            alerts.append(
                AlertCandidate(
                    rule_id="NET-001",
                    title=f"Port scan: {src} probed {len(ports)} ports on {dst}",
                    severity=Severity.high,
                    events=burst,
                    details={
                        "distinct_ports": len(ports),
                        "ports_sample": ports[:30],
                        "open_ports": sorted(
                            {e.dst_port for e in burst if e.outcome == "allowed" and e.dst_port}
                        ),
                    },
                    src_ip=src,
                    dedupe_key=f"{src}|{dst}|{burst[0].occurred_at.isoformat()}",
                )
            )
    return alerts


def denied_burst(events: Sequence[Event]) -> list[AlertCandidate]:
    alerts = []
    denied = [e for e in events if e.category == "network" and e.outcome == "denied"]
    for src, group in group_by(denied, lambda e: e.src_ip).items():
        for burst in bursts(group, DENIED_WINDOW, lambda w: len(w) >= DENIED_BURST):
            alerts.append(
                AlertCandidate(
                    rule_id="NET-002",
                    title=f"Denied connection burst: {len(burst)} blocked from {src}",
                    severity=Severity.medium,
                    events=burst,
                    details={"denied_connections": len(burst)},
                    src_ip=src,
                    dedupe_key=f"{src}|{burst[0].occurred_at.isoformat()}",
                )
            )
    return alerts


def known_bad_ip(events: Sequence[Event]) -> list[AlertCandidate]:
    alerts = []
    for ip, group in group_by(
        (e for e in events if e.src_ip in KNOWN_BAD_IPS), lambda e: e.src_ip
    ).items():
        alerts.append(
            AlertCandidate(
                rule_id="IOC-001",
                title=f"Activity from known-bad IP {ip}",
                severity=Severity.high,
                events=group,
                details={"events": len(group), "listed_reason": KNOWN_BAD_IPS[ip]},
                src_ip=ip,
                dedupe_key=ip,
            )
        )
    return alerts


RULES: list[Rule] = [
    Rule(
        "AUTH-001",
        "Brute force",
        "Repeated failed logins for one account from one IP",
        Severity.high,
        brute_force,
    ),
    Rule(
        "AUTH-002",
        "Password spraying",
        "One IP failing against many accounts",
        Severity.high,
        password_spray,
    ),
    Rule(
        "AUTH-003",
        "Success after failures",
        "A successful login right after repeated failures",
        Severity.critical,
        success_after_failures,
    ),
    Rule(
        "AUTH-004",
        "Off-hours login",
        "Successful login between 00:00 and 05:00 UTC",
        Severity.low,
        off_hours_login,
    ),
    Rule(
        "AUTH-005",
        "New source IP",
        "Successful login from an IP not seen for that user",
        Severity.medium,
        new_source_ip,
    ),
    Rule(
        "NET-001",
        "Port scan",
        "One source probing many ports on one host",
        Severity.high,
        port_scan,
    ),
    Rule(
        "NET-002",
        "Denied connection burst",
        "Many blocked connections from one source",
        Severity.medium,
        denied_burst,
    ),
    Rule(
        "IOC-001",
        "Known-bad IP",
        "Source IP appears on the threat blocklist",
        Severity.high,
        known_bad_ip,
    ),
]
RULES_BY_ID = {r.id: r for r in RULES}
