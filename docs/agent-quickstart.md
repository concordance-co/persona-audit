# Coding-Agent Quickstart

Use this when a local coding agent is helping someone run or adapt Persona Audit.

## What This Repo Does

Persona Audit loads conversation traces, joins optional score rows, and renders a dashboard for persona traits, emotion posture, outlier turns, sessions, users/cohorts, and scoring coverage.

The app has two parts:

- Backend: FastAPI in `backend/`
- Frontend: React/Vite in `frontend/`

## First Commands

```bash
git status --short --branch
test -f .env && sed -n 's/^\([^#=][^=]*\)=.*/\1/p' .env | sort
```

Never print `.env` values.

## Run The App

Backend:

```bash
uv run uvicorn backend.api.app:app --reload --port 8100
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`.

## Key Files

- `backend/api/app.py`: API routes
- `backend/api/models.py`: normalized `AuditTrace` and `AuditTurn`
- `backend/api/trace_source.py`: provider/source loading
- `backend/api/neon_scores.py`: Postgres/cache score loading
- `backend/api/provider.py`: provider metadata and copy
- `backend/workflows/`: scoring workflows
- `backend/scripts/`: import/upload scripts
- `frontend/src/routes/BehaviorAuditRoutes.jsx`: main dashboard routes
- `frontend/src/routes/behavior/`: frontend helpers/layout
- `frontend/src/styles.css`: dashboard styles
- `docs/adapter-contract.md`: normalized trace and score data contract
- `docs/llm-data-conversion-instructions.md`: instruction template for mapping arbitrary source data

## Dependency Note

Xenon is installed from the pinned Git dependency in `pyproject.toml`. Do not replace it with vendored code. If changing Xenon APIs, first push the Xenon commit, then update the pinned ref here.

## Common Tasks

Run tests:

```bash
uv run pytest
```

Build frontend:

```bash
cd frontend && npm run build
```

Use local data only:

```bash
BEHAVIOR_AUDIT_TRACE_SOURCE=local uv run uvicorn backend.api.app:app --reload --port 8100
```

Configure Postgres:

```bash
BEHAVIOR_AUDIT_DATABASE_URL=postgresql://user:pass@host:5432/dbname
```

The legacy `XENON_NEON_DATABASE_URL` still works, but public docs should prefer `BEHAVIOR_AUDIT_DATABASE_URL`.

## Add A New Data Source

1. Read `docs/adapter-contract.md`.
2. Use `docs/llm-data-conversion-instructions.md` to map the source data into the normalized shape.
3. Add a small loader or adapter under `backend/adapters/`, or upload normalized rows to Postgres-compatible trace tables.
4. Thread the provider through `backend/api/provider.py` and `backend/api/trace_source.py` when using an adapter.
5. Add focused tests for loader shape and provider routing.
6. Do not build a generic importer unless repeated real datasets justify it.

## Debug Empty Dashboard

1. Hit `/api/health`.
2. Hit `/api/audit/report?provider=<provider>`.
3. Check whether traces loaded before editing frontend code.
4. Check whether scores loaded before changing chart logic.
5. Use env var names only; do not print secrets.

## Private/Internal Boundary

Generated local score caches, local Hermes state, `.env`, Modal artifacts, and private source data should stay out of git.

