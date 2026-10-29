# SentinelAI

[![CI](https://github.com/sebibarrios/sentinelai/actions/workflows/ci.yml/badge.svg)](https://github.com/sebibarrios/sentinelai/actions/workflows/ci.yml)
[![CodeQL](https://github.com/sebibarrios/sentinelai/actions/workflows/codeql.yml/badge.svg)](https://github.com/sebibarrios/sentinelai/actions/workflows/codeql.yml)

AI-powered security operations platform: upload security logs, detect threats with deterministic rules, manage incidents, and get AI-generated explanations that are clearly separated from verified findings.

**Status:** feature-complete MVP, tested in CI; deployment is next. See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the design and [docs/SECURITY.md](docs/SECURITY.md) for the threat model and security controls.

**Stack:** Next.js · React · TypeScript · Tailwind CSS · shadcn/ui · FastAPI · PostgreSQL · SQLAlchemy · Alembic · OpenAI API · Docker · Pytest · Playwright · GitHub Actions

## Run locally

### With Docker

```bash
docker compose up --build --wait
docker compose exec backend python -m scripts.seed
```

Open http://localhost:3000. The seed script also loads a synthetic 24-hour log, so the dashboard has alerts to explore. More sample files are in [`sample-data/`](sample-data/).

AI features need `OPENAI_API_KEY` set for the backend (for example in a `.env` file next to `docker-compose.yml`). Without it, everything else works and the AI panels say AI isn't configured.

### Without Docker

You need Python 3.12+, Node 20.9+ and a PostgreSQL 16 database.

```bash
# Backend
cd backend
pip install -e ".[dev]"
export DATABASE_URL=postgresql+psycopg://sentinel:sentinel@localhost:5432/sentinelai
alembic upgrade head
python -m scripts.seed
uvicorn app.main:app --reload            # http://localhost:8000/api/docs

# Frontend (second terminal)
cd frontend
npm install
BACKEND_URL=http://localhost:8000 npm run dev   # http://localhost:3000
```

### Demo accounts

Created by the seed script (local password `SentinelDemo2026`, or `SEED_PASSWORD` if set):

| Email | Role | Can |
|---|---|---|
| admin@sentinel.demo | Admin | Everything, plus manage users and roles |
| analyst@sentinel.demo | Analyst | Create and work incidents |
| viewer@sentinel.demo | Viewer | Read only |

## Tests

Every push runs the full pipeline in GitHub Actions: lint, migration checks, unit and API tests, browser tests, a Docker build with a Compose smoke test, and CodeQL.

```bash
# Backend: unit + API tests against real PostgreSQL (needs a sentinelai_test database)
cd backend && pytest --cov=app

# Frontend: lint, types, production build
cd frontend && npm run lint && npm run typecheck && npm run build

# End-to-end: starts the API and web app itself, resets a sentinelai_e2e database,
# and uses a deterministic offline AI fixture (no OpenAI calls)
cd frontend && npx playwright install chromium && npm run test:e2e
```

## Configuration for deployment

Set these on the hosting platform, never in the repository. The backend refuses to start in production without the secrets.

| Variable | Where | Purpose |
|---|---|---|
| `ENVIRONMENT=production` | API | Enables production checks, `Secure` cookies, HSTS; turns off API docs |
| `DATABASE_URL` | API | PostgreSQL connection string (`postgres://` URLs from providers are accepted) |
| `JWT_SECRET` | API | Long random value that signs session tokens |
| `PROXY_SHARED_SECRET` | API **and** web | Same long random value on both; the API refuses requests that don't come through the web app |
| `OPENAI_API_KEY` | API | Enables the AI analyst (optional) |
| `BACKEND_URL` | web (build time) | The API's URL; Next.js forwards `/api/*` there |
| `CLIENT_IP_HEADER` | web | Header your host sets to the visitor's IP (e.g. `x-real-ip` on Vercel), used for per-IP rate limits (off without it; per-account limits always apply) |

Generate secrets with `python -c "import secrets; print(secrets.token_urlsafe(48))"`.
