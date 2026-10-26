"""Deterministic synthetic security logs for demos and tests.

Background noise: ~40 employees logging in during business hours from their usual
IP, the occasional mistyped password, and routine allowed network traffic.
Planted on top: a handful of attack scenarios, each designed to trigger specific
detection rules. All IPs are in documentation (RFC 5737) or private ranges and all
names are invented, so nothing resembles a real person or network.
"""

import random
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

FIRST = ["alex", "sam", "jordan", "taylor", "casey", "riley", "morgan", "jamie", "drew", "avery"]
LAST = ["nguyen", "patel", "garcia", "kim", "smith", "lopez", "chen", "brown", "silva", "ali"]
COUNTRIES = ["US", "US", "US", "US", "CA", "GB"]
UA = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/130.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_6) Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) Firefox/131.0",
]
SERVERS = ["10.0.1.10", "10.0.1.11", "10.0.2.20", "10.0.3.5"]
COMMON_PORTS = [443, 443, 443, 80, 22, 3389, 5432]

# Scenario actors. IOC_IP must be on the detection blocklist.
BRUTE_FORCE_IP = "203.0.113.45"
SPRAY_IP = "198.51.100.23"
SCAN_IP = "192.0.2.77"
SCAN_TARGET = "10.0.4.12"
IOC_IP = "203.0.113.66"


@dataclass
class SyntheticLog:
    rows: list[dict]
    scenarios: list[str]


def _iso(t: datetime) -> str:
    return t.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def generate(end: datetime | None = None, seed: int = 7, hours: int = 24) -> SyntheticLog:
    rng = random.Random(seed)  # noqa: S311 - reproducible demo data, not security-sensitive
    end = (end or datetime.now(UTC)).replace(microsecond=0)
    start = end - timedelta(hours=hours)
    rows: list[dict] = []

    def auth(t, user, ip, outcome, country="US", ua=None):
        rows.append(
            {
                "timestamp": _iso(t),
                "category": "auth",
                "action": "login",
                "outcome": outcome,
                "username": user,
                "src_ip": ip,
                "dst_ip": "10.0.0.5",
                "dst_port": 443,
                "protocol": "tcp",
                "user_agent": ua or rng.choice(UA),
                "country": country,
            }
        )

    def net(t, src, dst, port, outcome, country=""):
        rows.append(
            {
                "timestamp": _iso(t),
                "category": "network",
                "action": "connection",
                "outcome": outcome,
                "username": "",
                "src_ip": src,
                "dst_ip": dst,
                "dst_port": port,
                "protocol": "tcp",
                "user_agent": "",
                "country": country,
            }
        )

    # --- Background: normal employees -------------------------------------------------
    users = [f"{f[0]}{last}" for f in FIRST for last in LAST[:4]]  # 40 usernames
    home_ip = {u: f"10.20.{i // 250}.{(i % 250) + 2}" for i, u in enumerate(users)}
    home_country = {u: rng.choice(COUNTRIES) for u in users}
    day = start.replace(hour=0, minute=0, second=0)
    while day < end:
        for u in users:
            if rng.random() < 0.15:
                continue  # not everyone logs in every day
            t = day + timedelta(hours=rng.uniform(8, 18.5))
            if not (start <= t < end):
                continue
            if rng.random() < 0.08:  # a single typo, then success
                auth(
                    t - timedelta(seconds=rng.randint(10, 40)),
                    u,
                    home_ip[u],
                    "failure",
                    home_country[u],
                )
            auth(t, u, home_ip[u], "success", home_country[u])
        day += timedelta(days=1)

    for _ in range(hours * 60):
        t = start + timedelta(seconds=rng.uniform(0, hours * 3600))
        src = rng.choice(list(home_ip.values()))
        net(t, src, rng.choice(SERVERS), rng.choice(COMMON_PORTS), "allowed")

    # Scenario timing: anchored relative to `end` so they land during the window.
    base = end - timedelta(hours=min(hours, 20))
    scenarios: list[str] = []

    # 1. Brute force (AUTH-001): 12 failures for one user from one IP in ~4 minutes.
    t = base + timedelta(hours=2, minutes=14)
    for i in range(12):
        auth(
            t + timedelta(seconds=i * 20),
            "admin",
            BRUTE_FORCE_IP,
            "failure",
            "RU",
            "python-requests/2.32",
        )
    scenarios.append("Brute force against the admin account from 203.0.113.45")

    # 2. Password spraying (AUTH-002) that succeeds (AUTH-003) from a new IP (AUTH-005).
    t = base + timedelta(hours=6, minutes=3)
    targets = ["aknguyen", "spatel", "jdoe", "tkim", "rsilva", "cchen", "dlopez", "jdoe", "jdoe"]
    for i, victim in enumerate(targets):
        auth(t + timedelta(seconds=i * 35), victim, SPRAY_IP, "failure", "NL", "curl/8.4.0")
    auth(t + timedelta(minutes=6), "jdoe", SPRAY_IP, "success", "NL", "curl/8.4.0")
    scenarios.append("Password spray from 198.51.100.23 ending in a jdoe login")
    # jdoe's normal baseline login earlier that day, so the spray IP is "new".
    auth(base + timedelta(hours=1), "jdoe", "10.20.9.9", "success", "US")

    # 3. Port scan (NET-001) with many denied connections (NET-002).
    t = base + timedelta(hours=9, minutes=40)
    ports = rng.sample(range(1, 1024), 40)
    for i, port in enumerate(ports):
        outcome = "allowed" if port in (22, 80, 443) else "denied"
        net(t + timedelta(seconds=i * 3), SCAN_IP, SCAN_TARGET, port, outcome, "CN")
    scenarios.append("Port scan of 10.0.4.12 from 192.0.2.77")

    # 4. Off-hours privileged login (AUTH-004).
    t = (end - timedelta(days=1)).replace(hour=3, minute=12, second=0)
    if t < start:
        t += timedelta(days=1)
    if t < end:
        auth(t, "svc_backup", "10.20.200.10", "success", "US")
        scenarios.append("Off-hours login by svc_backup")

    # 5. Known-bad IP (IOC-001) making a few connections.
    t = base + timedelta(hours=12)
    for i in range(4):
        net(t + timedelta(minutes=i * 7), IOC_IP, "10.0.1.10", 443, "allowed", "RU")
    scenarios.append("Traffic from blocklisted IP 203.0.113.66")

    rows.sort(key=lambda r: r["timestamp"])
    return SyntheticLog(rows=rows, scenarios=scenarios)
