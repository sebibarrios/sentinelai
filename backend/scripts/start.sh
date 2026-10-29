#!/bin/sh
# Container entrypoint: migrate, optionally seed, then serve.
set -e
alembic upgrade head
# Public demo: create the demo data once, and restore the shared demo logins on every start.
if [ -n "$SEED_PASSWORD" ]; then
  python -m scripts.seed
fi
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" --proxy-headers
