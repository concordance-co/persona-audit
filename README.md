# Persona Audit

Persona Audit is a FastAPI backend plus React dashboard for inspecting LLM conversation behavior across persona traits, emotion posture, outliers, sessions, and scoring coverage.

## Layout

```text
backend/    Python backend, source adapters, scoring workflows, upload scripts
frontend/   React dashboard
data/       bundled public-safe score caches and local demo artifacts
reports/    bundled public-safe report artifacts
docs/       setup, release, and coding-agent notes
tests/      backend tests
```

`frontend/dist/` is intentionally tracked as the bundled dashboard build. `frontend/node_modules/` stays local-only and ignored.

## Requirements

- Python 3.13+
- `uv`
- Node.js 20+
- Xenon, installed from the pinned Git dependency in `pyproject.toml`
- Optional: Postgres or Neon for live trace/score tables
- Optional: Modal auth and `HF_TOKEN` for scoring workflows

`persona-audit` pins Xenon by Git commit for reproducible local installs. Update that commit only after the corresponding Xenon branch/tag is pushed.

## Run Locally

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

Health check:

```bash
curl http://localhost:8100/api/health
```

## Configuration

Copy `.env.example` to `.env` and fill only the values you need.

```bash
cp .env.example .env
```

Database:

- `BEHAVIOR_AUDIT_DATABASE_URL`: public-facing Postgres-compatible DSN.
- `XENON_NEON_DATABASE_URL`: legacy compatibility alias, still supported.

Examples:

```bash
BEHAVIOR_AUDIT_DATABASE_URL=postgresql://persona:persona@localhost:5432/persona_audit
BEHAVIOR_AUDIT_DATABASE_URL=postgresql://user:pass@host.neon.tech/dbname?sslmode=require
```

Local Postgres:

```bash
docker compose up -d postgres
```

No database is required for the bundled local demo path. Set `BEHAVIOR_AUDIT_TRACE_SOURCE=local` to force local loaders and skip the database.

## Bring Your Own Data

The stable normalized shape is:

- `AuditTrace`: one conversation/session.
- `AuditTurn`: one message/tool turn inside a trace.

Use [docs/adapter-contract.md](docs/adapter-contract.md) for the required trace shape and adapter expectations. Use [docs/llm-data-conversion-instructions.md](docs/llm-data-conversion-instructions.md) when asking a coding agent to map a new source into that shape.

The intended public path is:

1. Convert your conversations into the normalized trace shape.
2. Add a small source-specific adapter or upload normalized trace/turn rows to a Postgres-compatible database.
3. Run scoring if you want trait/emotion activations.
4. Open the dashboard with your provider selected.

There is intentionally no one-size-fits-all importer. Source data varies too much; the stable contract is the normalized shape and the small adapter boundary.

## Scoring

Remote scoring uses Xenon workflows on Modal. You need Modal auth and `HF_TOKEN`.

Plan workflows:

```bash
uv run python -m pipelines_v2.cli workflow plan --file backend/workflows/tau2_scoring.py
uv run python -m pipelines_v2.cli workflow plan --file backend/workflows/hermes_scoring.py
```

Run workflows:

```bash
uv run python -m pipelines_v2.cli workflow run --file backend/workflows/tau2_scoring.py --logging INFO
uv run python -m pipelines_v2.cli workflow run --file backend/workflows/hermes_scoring.py --logging INFO
```

Import/upload scripts can write local score caches or upload rows to Postgres-compatible tables. They create tables when needed.

## Privacy Boundary

Before publishing a public repo:

- Do not commit `.env`, local Hermes state, generated local score caches, Modal artifacts, or private source data.
- Run the release checklist in [docs/release-checklist.md](docs/release-checklist.md).

## Verify

```bash
uv run pytest
uv run python -m py_compile backend/api/app.py backend/api/trace_source.py backend/api/neon_scores.py backend/workflows/tau2_scoring.py backend/workflows/hermes_scoring.py
cd frontend && npm run build
```
