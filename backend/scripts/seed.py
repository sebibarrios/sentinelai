"""Create demo users and sample incidents.

Usage:  python -m scripts.seed
Demo passwords come from SEED_PASSWORD (default only allowed outside production).
Safe to run more than once: existing users and incidents are left alone.
"""

import os
import sys

from sqlalchemy import func, select

from app.core.config import get_settings
from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models import Incident, User
from app.models.enums import IncidentStatus, Role, Severity
from app.schemas.incident import IncidentCreate, IncidentUpdate
from app.services import incidents as svc

DEMO_USERS = [
    ("admin@sentinel.demo", "Avery Admin", Role.admin),
    ("analyst@sentinel.demo", "Jordan Analyst", Role.analyst),
    ("viewer@sentinel.demo", "Riley Viewer", Role.viewer),
]

DEMO_INCIDENTS = [
    (
        "Brute-force attempts against VPN accounts",
        "Repeated failed logins from 203.0.113.0/24 against several VPN users.",
        Severity.high,
        IncidentStatus.investigating,
    ),
    (
        "Successful login after password spraying",
        "jdoe logged in from 198.51.100.23 after 14 failures across multiple accounts.",
        Severity.critical,
        IncidentStatus.open,
    ),
    (
        "Port scan from external host",
        "192.0.2.77 probed 40 ports on the bastion host within two minutes.",
        Severity.medium,
        IncidentStatus.contained,
    ),
    (
        "Off-hours admin login",
        "Admin console login at 03:12 UTC; confirmed as scheduled maintenance.",
        Severity.low,
        IncidentStatus.closed,
    ),
]


def main() -> None:
    settings = get_settings()
    password = os.environ.get("SEED_PASSWORD")
    if not password:
        if settings.is_production:
            sys.exit("Set SEED_PASSWORD to seed a production database.")
        password = "SentinelDemo2026"  # noqa: S105 - local development only

    db = SessionLocal()
    try:
        users: dict[Role, User] = {}
        for email, name, role in DEMO_USERS:
            user = db.scalar(select(User).where(User.email == email))
            if user is None:
                user = User(
                    email=email, full_name=name, role=role, password_hash=hash_password(password)
                )
                db.add(user)
                db.commit()
                print(f"created {role.value:8} {email}")
            users[role] = user

        if (db.scalar(select(func.count()).select_from(Incident)) or 0) == 0:
            analyst = users[Role.analyst]
            for title, description, severity, status in DEMO_INCIDENTS:
                inc = svc.create_incident(
                    db,
                    IncidentCreate(
                        title=title,
                        description=description,
                        severity=severity,
                        assignee_id=analyst.id,
                    ),
                    analyst,
                )
                if status != IncidentStatus.open:
                    svc.update_incident(db, inc, IncidentUpdate(status=status), analyst)
            svc.add_note(
                db,
                inc,
                "Verified with the change calendar; no further action.",
                analyst,
            )
            print(f"created {len(DEMO_INCIDENTS)} demo incidents")
    finally:
        db.close()


if __name__ == "__main__":
    main()
