from collections.abc import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

engine = create_engine(get_settings().database_url, pool_pre_ping=True)


@event.listens_for(engine, "connect")
def _use_utc(dbapi_connection, _record) -> None:
    """Pin every connection to UTC.

    Dashboard buckets use date_trunc, which follows the session time zone; a managed
    database configured for another zone would otherwise shift or empty the charts.
    A SET statement (rather than a startup option) also works through PgBouncer-style
    connection poolers that reject startup parameters.
    """
    with dbapi_connection.cursor() as cursor:
        cursor.execute("SET TIME ZONE 'UTC'")
    dbapi_connection.commit()


SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    """FastAPI dependency: one session per request, always closed."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
