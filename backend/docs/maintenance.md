# Maintenance

Keep the repo layout simple:

```text
backend/    Python backend and workflows
frontend/   React dashboard
data/       bundled score caches
reports/    bundled report artifacts
```

## Rules

- Keep Xenon as the backend dependency. Do not copy `pipelines_v2` or `papers.voice.*` into this repo.
- Do not reintroduce `products.behavior_audit` imports.
- Do not commit `.env`, private source files, or generated caches.
- Do not commit local Hermes state, generated local score caches, or private source data.
- Keep `frontend/dist/` tracked unless the app serving/deployment model changes.
- Keep API routes stable unless the task explicitly changes them.
- Keep Tau2 and Hermes workflow plan commands working.
- Keep `.env.example` aligned with env vars read by backend loaders, upload scripts, and workflows.
- Keep `docs/adapter-contract.md` aligned with `backend/api/models.py`.

## Data Loading

Order:

1. Load `.env` from repo root.
2. Use Postgres-compatible live data when `BEHAVIOR_AUDIT_DATABASE_URL` or legacy `XENON_NEON_DATABASE_URL` is set.
3. Fall back to bundled caches and smoke data.

Important local paths:

- `data/neon_score_summaries/`
- `data/supplemental_scores/`
- `reports/behavior_audit_public/`
- `frontend/dist/`

## Verify

```bash
uv run pytest
uv run python -m py_compile backend/api/app.py backend/workflows/tau2_scoring.py backend/workflows/hermes_scoring.py
uv run python -m pipelines_v2.cli workflow plan --file backend/workflows/tau2_scoring.py
uv run python -m pipelines_v2.cli workflow plan --file backend/workflows/hermes_scoring.py
cd frontend && npm run build
```
