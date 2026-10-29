"""The seed script runs on every start of the public demo, so it must be safe to repeat."""

from sqlalchemy import func, select

from app.core.security import verify_password
from app.models import Incident, LogUpload, User
from app.models.enums import Role
from scripts import seed


def _user(db, email: str) -> User:
    db.expire_all()
    return db.scalar(select(User).where(User.email == email))


def test_seed_is_repeatable_and_keeps_the_admin_password_separate(db, monkeypatch):
    monkeypatch.setenv("SEED_PASSWORD", "shared-demo-pass")
    monkeypatch.setenv("SEED_ADMIN_PASSWORD", "private-admin-pass")
    seed.main()
    seed.main()

    assert db.scalar(select(func.count()).select_from(User)) == 3
    assert db.scalar(select(func.count()).select_from(Incident)) == len(seed.DEMO_INCIDENTS)
    assert db.scalar(select(func.count()).select_from(LogUpload)) == 1
    admin = _user(db, "admin@sentinel.demo")
    assert verify_password("private-admin-pass", admin.password_hash)
    assert not verify_password("shared-demo-pass", admin.password_hash)
    assert verify_password("shared-demo-pass", _user(db, "analyst@sentinel.demo").password_hash)


def test_reseeding_undoes_a_visitor_tampering_with_shared_demo_logins(db, monkeypatch):
    monkeypatch.setenv("SEED_PASSWORD", "shared-demo-pass")
    seed.main()
    viewer = _user(db, "viewer@sentinel.demo")
    viewer.password_hash = "changed-by-a-visitor"
    viewer.role = Role.admin
    viewer.is_active = False
    version = viewer.session_version
    db.commit()

    seed.main()

    viewer = _user(db, "viewer@sentinel.demo")
    assert verify_password("shared-demo-pass", viewer.password_hash)
    assert viewer.role == Role.viewer
    assert viewer.is_active
    assert viewer.session_version == version + 1  # the visitor's session is ended
