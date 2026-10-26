from datetime import UTC, datetime, timedelta

import pytest

from app.detection import rules
from app.detection.base import Event
from app.detection.engine import run_rules
from app.ingest.synthetic import generate

T0 = datetime(2026, 10, 20, 12, 0, tzinfo=UTC)
_ref = iter(range(1_000_000))


def auth(offset_s, user, ip, outcome="failure", at=T0):
    return Event(next(_ref), at + timedelta(seconds=offset_s), "auth", outcome, ip, username=user)


def net(offset_s, src, dst, port, outcome="denied"):
    return Event(
        next(_ref),
        T0 + timedelta(seconds=offset_s),
        "network",
        outcome,
        src,
        dst_ip=dst,
        dst_port=port,
    )


def ids(alerts):
    return [a.rule_id for a in alerts]


# --- AUTH-001 brute force ------------------------------------------------------------


def test_brute_force_triggers_at_threshold():
    events = [auth(i * 30, "bob", "203.0.113.1") for i in range(5)]
    [alert] = rules.brute_force(events)
    assert alert.username == "bob" and len(alert.events) == 5


def test_brute_force_below_threshold_or_spread_out_is_quiet():
    assert rules.brute_force([auth(i * 30, "bob", "203.0.113.1") for i in range(4)]) == []
    # 5 failures, but 4 minutes apart each -> never 5 inside 10 minutes
    assert rules.brute_force([auth(i * 240, "bob", "203.0.113.1") for i in range(5)]) == []


def test_sustained_attack_is_one_alert_and_separate_attacks_are_two():
    sustained = [auth(i * 60, "bob", "203.0.113.1") for i in range(30)]  # 30 min straight
    assert len(rules.brute_force(sustained)) == 1
    two = [auth(i * 10, "bob", "203.0.113.1") for i in range(5)] + [
        auth(7200 + i * 10, "bob", "203.0.113.1") for i in range(5)
    ]
    assert len(rules.brute_force(two)) == 2


def test_brute_force_groups_by_user_and_ip():
    mixed = [auth(i, f"user{i}", "203.0.113.1") for i in range(5)]  # one each, 5 users
    assert rules.brute_force(mixed) == []


# --- AUTH-002 password spraying -----------------------------------------------------


def test_password_spray():
    events = [auth(i * 20, f"user{i}", "198.51.100.9") for i in range(6)]
    [alert] = rules.password_spray(events)
    assert alert.details["distinct_usernames"] == 6


def test_many_failures_on_one_user_is_not_spraying():
    assert rules.password_spray([auth(i, "bob", "198.51.100.9") for i in range(20)]) == []


# --- AUTH-003 success after failures ------------------------------------------------


def test_success_after_failures_is_critical():
    events = [auth(i * 10, "eve", "198.51.100.9") for i in range(3)]
    events.append(auth(60, "eve", "198.51.100.9", "success"))
    [alert] = rules.success_after_failures(events)
    assert alert.severity.value == "critical" and len(alert.events) == 4


def test_old_failures_do_not_count():
    events = [auth(i * 10, "eve", "198.51.100.9") for i in range(3)]
    events.append(auth(3600, "eve", "10.0.0.1", "success"))
    assert rules.success_after_failures(events) == []


# --- AUTH-004 off-hours / AUTH-005 new IP ------------------------------------------


def test_off_hours_one_alert_per_user_per_day():
    night = T0.replace(hour=2)
    events = [
        auth(0, "svc", "10.0.0.1", "success", at=night),
        auth(600, "svc", "10.0.0.1", "success", at=night),
    ]
    [alert] = rules.off_hours_login(events)
    assert alert.details["logins"] == 2
    assert rules.off_hours_login([auth(0, "svc", "10.0.0.1", "success")]) == []  # noon


def test_new_source_ip_needs_a_baseline():
    assert rules.new_source_ip([auth(0, "amy", "10.0.0.1", "success")]) == []
    events = [
        auth(0, "amy", "10.0.0.1", "success"),
        auth(60, "amy", "10.0.0.1", "success"),
        auth(120, "amy", "198.51.100.4", "success"),
        auth(180, "amy", "198.51.100.4", "success"),  # same new IP again: no second alert
    ]
    [alert] = rules.new_source_ip(events)
    assert alert.details == {"known_ips": ["10.0.0.1"], "new_ip": "198.51.100.4"}


# --- NET-001 / NET-002 / IOC-001 ---------------------------------------------------


def test_port_scan_counts_distinct_ports():
    scan = [net(i * 5, "192.0.2.7", "10.0.0.5", 1000 + i) for i in range(15)]
    [alert] = rules.port_scan(scan)
    assert alert.details["distinct_ports"] == 15
    repeated = [net(i, "192.0.2.7", "10.0.0.5", 443, "allowed") for i in range(100)]
    assert rules.port_scan(repeated) == []  # busy but legitimate


def test_denied_burst():
    assert ids(rules.denied_burst([net(i, "192.0.2.7", "10.0.0.5", 22) for i in range(20)])) == [
        "NET-002"
    ]
    assert rules.denied_burst([net(i, "192.0.2.7", "10.0.0.5", 22) for i in range(19)]) == []


def test_known_bad_ip():
    [alert] = rules.known_bad_ip([net(0, "203.0.113.66", "10.0.0.5", 443, "allowed")])
    assert "Synthetic feed" in alert.details["listed_reason"]


# --- Engine over realistic data -----------------------------------------------------


EXPECTED = [
    "AUTH-001",
    "AUTH-002",
    "AUTH-003",
    "AUTH-004",
    "AUTH-005",
    "IOC-001",
    "NET-001",
    "NET-002",
]


def _to_events(log):
    return [
        Event(
            i,
            datetime.fromisoformat(r["timestamp"]),
            r["category"],
            r["outcome"],
            r["src_ip"],
            username=r["username"] or None,
            dst_ip=r["dst_ip"],
            dst_port=r["dst_port"],
        )
        for i, r in enumerate(log.rows)
    ]


@pytest.mark.parametrize("seed", range(1, 11))
def test_each_planted_attack_found_once_and_no_false_positives(seed):
    """Background noise (≈1,500 events) must stay quiet; each planted scenario fires once."""
    alerts = run_rules(_to_events(generate(seed=seed, end=T0)))
    assert sorted(ids(alerts)) == EXPECTED


def test_dedupe_keys_are_stable_across_runs():
    log = generate(seed=3, end=T0)
    first = {a.dedupe_key for a in run_rules(_to_events(log))}
    second = {a.dedupe_key for a in run_rules(_to_events(log))}
    assert first == second and len(first) == len(EXPECTED)
