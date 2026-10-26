import os

# Configure the app for tests *before* importing it.
os.environ.setdefault(
    "DATABASE_URL", "postgresql+psycopg://sentinel:sentinel@localhost:5432/sentinelai_test"
)
os.environ["ENVIRONMENT"] = "test"
os.environ["JWT_SECRET"] = "test-secret-that-is-at-least-32-bytes-long"
os.environ["OPENAI_API_KEY"] = ""

from collections.abc import Callable, Iterator  # noqa: E402
from pathlib import Path  # noqa: E402

import pytest  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from alembic import command  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.db.session import SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import User  # noqa: E402
from app.models.enums import Role  # noqa: E402

PASSWORD = "CorrectHorse42"


@pytest.fixture(scope="session", autouse=True)
def _migrate() -> Iterator[None]:
    """Run the real Alembic migrations once, so tests also verify the migration chain."""
    cfg = Config(str(Path(__file__).parents[1] / "alembic.ini"))
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")
    yield


@pytest.fixture(autouse=True)
def _clean_tables() -> Iterator[None]:
    yield
    tables = ", ".join(t.name for t in reversed(Base.metadata.sorted_tables))
    with engine.begin() as conn:
        conn.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))


@pytest.fixture
def db() -> Iterator[Session]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def make_user(db: Session) -> Callable[..., User]:
    def _make(email: str = "analyst@example.com", role: Role = Role.analyst, **kw) -> User:
        user = User(
            email=email,
            full_name=kw.get("full_name", email.split("@")[0].title()),
            password_hash=hash_password(PASSWORD),
            role=role,
            is_active=kw.get("is_active", True),
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    return _make


@pytest.fixture
def client() -> Iterator[TestClient]:
    # Like the real frontend, send the CSRF header on every request.
    with TestClient(app, headers={"X-Requested-With": "pytest"}) as c:
        yield c


@pytest.fixture
def login(client: TestClient) -> Callable[[str], TestClient]:
    """Log in as the given email; the session cookie stays on the client."""

    def _login(email: str) -> TestClient:
        r = client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
        assert r.status_code == 200, r.text
        return client

    return _login


@pytest.fixture
def analyst_client(make_user, login) -> TestClient:
    make_user("analyst@example.com", Role.analyst)
    return login("analyst@example.com")
