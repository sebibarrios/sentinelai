# SentinelAI

AI-powered security operations platform: upload security logs, detect threats with deterministic rules, manage incidents, and get AI-generated explanations that are clearly separated from verified findings.

**Status:** in active development. Incident management, authentication and role-based access are working; log analysis and AI features are next. See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the design.

**Stack:** Next.js · React · TypeScript · Tailwind CSS · shadcn/ui · FastAPI · PostgreSQL · SQLAlchemy · Alembic · OpenAI API · Docker · Pytest · Playwright · GitHub Actions

## Run locally

### With Docker

```bash
docker compose up --build
docker compose exec backend python -m scripts.seed
```

Open http://localhost:3000.

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

```bash
cd backend && pytest --cov=app        # needs a sentinelai_test database
cd frontend && npm run lint && npx tsc --noEmit && npm run build
```
