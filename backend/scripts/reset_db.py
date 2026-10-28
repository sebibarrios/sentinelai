"""Drop and recreate the schema, then seed demo data. For end-to-end test runs only.

Usage:  python -m scripts.reset_db
Refuses to run unless the database name ends in _e2e or _test, so it can't wipe a
development or production database by accident.
"""

import sys

from alembic.config import Config
from sqlalchemy.engine import make_url

from alembic import command
from app.core.config import get_settings

ALLOWED_SUFFIXES = ("_e2e", "_test")


def main() -> None:
    settings = get_settings()
    name = make_url(settings.database_url).database or ""
    if settings.is_production or not name.endswith(ALLOWED_SUFFIXES):
        sys.exit(f"Refusing to reset database {name!r}: name must end in {ALLOWED_SUFFIXES}.")

    cfg = Config("alembic.ini")
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")

    from scripts import seed

    seed.main()
    print(f"reset and seeded {name}")


if __name__ == "__main__":
    main()
