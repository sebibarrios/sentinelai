# SentinelAI

[![CI](https://github.com/sebibarrios/sentinelai/actions/workflows/ci.yml/badge.svg)](https://github.com/sebibarrios/sentinelai/actions/workflows/ci.yml)
[![CodeQL](https://github.com/sebibarrios/sentinelai/actions/workflows/codeql.yml/badge.svg)](https://github.com/sebibarrios/sentinelai/actions/workflows/codeql.yml)

A security operations platform for small teams: upload authentication and network logs, detect attacks with deterministic rules, investigate alerts down to the log lines that caused them, and manage incidents. An optional AI analyst explains alerts and drafts incident reports, and its output is always kept separate from verified findings.

**Live demo: [sentinelai-sage.vercel.app](https://sentinelai-sage.vercel.app)**

| Demo login | Password | Role |
|---|---|---|
| `analyst@sentinel.demo` | `Basin-Raven-Amber-54` | Analyst: work alerts, create and update incidents, upload logs |
| `viewer@sentinel.demo` | `Basin-Raven-Amber-54` | Viewer: read-only |

The demo runs on free hosting, so the first request after a quiet period can take about a minute while the API wakes up. Demo accounts are reset whenever the API starts, and all data is synthetic. AI analysis is turned off on the public demo (no API key); see [AI analyst](#ai-analyst) for how it works.

![Dashboard](docs/screenshots/dashboard.png)

## What it does

1. **Ingest.** Upload a CSV or NDJSON log file (up to 10 MB / 100,000 rows). Every row is validated, with bad rows reported line by line, and the import is all-or-nothing. A 100,000-row file is parsed, stored, and run through every detection rule in about 6 seconds.
2. **Detect.** Eight rules flag what happened, each one a pure, unit-tested function:

   | Rule | Detects |
   |---|---|
   | AUTH-001 | Brute force against one account |
   | AUTH-002 | Password spraying across accounts |
   | AUTH-003 | Successful login right after failures (critical) |
   | AUTH-004 | Off-hours login |
   | AUTH-005 | Login from a new source IP |
   | NET-001 | Port scan |
   | NET-002 | Burst of denied connections |
   | IOC-001 | Traffic from a known-bad IP |

   Overlapping detections merge into one alert, and re-uploading the same data never creates duplicates.
3. **Investigate.** Every alert links to its evidence rows. Dashboard figures drill down to the matching alerts and events.
4. **Respond.** Analysts promote alerts to incidents, assign owners, move them through open → investigating → contained → closed, and leave notes. Every change is recorded in the incident's history.

| Alert with its evidence | Incidents |
|---|---|
| ![Alert detail](docs/screenshots/alert-detail.png) | ![Incidents](docs/screenshots/incidents.png) |

## AI analyst

The AI explains alerts and drafts incident reports, but it never decides what's malicious. The rules do that. Model output is:

- **labeled and stored separately** from verified findings, with the model, prompt version, and requester, and it can't change an alert or incident;
- **checked against the evidence:** indicators in a report that don't appear in the input data are removed, and the analyst sees how many;
- **protected from prompt injection:** log fields are attacker-controlled, so they reach the model only inside an escaped data block;
- **schema-validated, rate-limited, and cached**, so identical evidence isn't sent to the model twice.

It uses the OpenAI API with structured outputs. Set `OPENAI_API_KEY` on the API to turn it on. The browser tests use a deterministic offline fixture instead, so CI never calls OpenAI.

## Security

The full threat model, with the control and the proving test for each threat, is in [docs/SECURITY.md](docs/SECURITY.md). Highlights:

- Argon2id password hashing; sessions in `httpOnly` cookies, revoked on sign-out, password change, and deactivation
- Account lockout counted atomically, so 30 simultaneous guesses can't exceed the 5-attempt limit (regression-tested); per-IP limits against password spraying
- Role-based access (admin / analyst / viewer) enforced on the server for every protected route
- The API refuses any request that doesn't come through the web app (shared-secret proxy); CSRF header check; Content-Security-Policy, HSTS, and clickjacking protection
- Upload validation (type, size, content, row-level schema), with files never written to disk

## Architecture

```mermaid
flowchart LR
    B[Browser] -->|HTTPS| W["Next.js web app<br/>Vercel"]
    W -->|"/api/* + shared secret"| A["FastAPI API<br/>Render"]
    A --> D[("PostgreSQL<br/>Neon")]
    A -.->|optional| O[OpenAI API]
```

The browser only talks to the Next.js origin, which forwards `/api/*` to FastAPI. That keeps the session cookie first-party and the API unreachable from outside. Design details are in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

**Stack:** Next.js 16, React 19, TypeScript, Tailwind CSS, shadcn/ui, TanStack Query · FastAPI, SQLAlchemy 2.0, Alembic, Pydantic · PostgreSQL · OpenAI API · Docker · Pytest, Playwright · GitHub Actions, CodeQL, Dependabot

## Testing

Every push runs lint, type checks, migration checks, **153 backend tests (97% coverage, 90% minimum)**, **19 browser tests** against a production build, a Docker Compose smoke test, and CodeQL. The API deploys only after CI passes.

```bash
# Backend: unit + API tests against real PostgreSQL (needs a sentinelai_test database)
cd backend && pytest --cov=app

# Frontend: lint, types, production build
cd frontend && npm run lint && npm run typecheck && npm run build

# End-to-end: starts the API and web app, resets a sentinelai_e2e database,
# and uses the offline AI fixture
cd frontend && npx playwright install chromium && npm run test:e2e
```

## Run locally

### With Docker

```bash
docker compose up --build --wait
docker compose exec backend python -m scripts.seed
```

Open http://localhost:3000 and sign in with a demo account (local password `SentinelDemo2026`). The seed script loads a synthetic 24-hour log so the dashboard has alerts to explore; more sample files are in [`sample-data/`](sample-data/).

### Without Docker

You need Python 3.12+, Node 20.9+ and PostgreSQL 16.

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

## Deployment

The live demo is the web app on Vercel, the API on Render (Docker, defined in [`render.yaml`](render.yaml)), and PostgreSQL on Neon, all on free plans. Secrets are set on the hosts, never in the repository, and the API refuses to start in production without them.

| Variable | Where | Purpose |
|---|---|---|
| `ENVIRONMENT=production` | API | Production checks, `Secure` cookies, HSTS; turns off API docs |
| `DATABASE_URL` | API | PostgreSQL connection string. Use a direct (unpooled) connection |
| `JWT_SECRET` | API | Signs session tokens (generated by Render) |
| `PROXY_SHARED_SECRET` | API **and** web | Same value on both; the API refuses requests that don't carry it (generated by Render) |
| `SEED_PASSWORD` / `SEED_ADMIN_PASSWORD` | API | Optional: create the demo data and restore the shared demo logins on each start; the admin gets its own password |
| `OPENAI_API_KEY` | API | Optional: turns on the AI analyst |
| `BACKEND_URL` | web (build time) | The API's URL; Next.js forwards `/api/*` there |
| `CLIENT_IP_HEADER` | web | Header the host sets to the visitor's IP (`x-real-ip` on Vercel), for per-IP rate limits |
