# Agent Notes

Operating context for coding agents. Commands and setup live in
[README.md](README.md) — this file covers the map and the invariants.

## Repo Map

```text
backend/api/registry.py      ProviderSpec + resolution — THE extension point
backend/api/providers/       one module per data source (tau2, hermes, persona_demo)
backend/api/trace_source.py  registry-driven trace loading (local or Postgres)
backend/api/scores/          score access; __init__ docstring is the module map
backend/api/audit_data.py    report assembly (composes flags/persona/session modules)
backend/api/flags.py         lexical flag heuristics + module scoring
backend/api/persona_analytics.py  persona-vector math, track comparison, outliers
backend/api/session_analytics.py  session/user view models
backend/api/paper_assets.py  sole import boundary for papers.voice assets
backend/api/cache.py         registered data caches; POST /api/cache/clear
backend/adapters/            source-specific parsing (hermes state.db)
backend/workflows/           Modal scoring workflows; common.py = shared config/builders
backend/scripts/             run_xenon_workflow.sh, bootstrap_modal.py, upload CLIs
backend/scores_io.py         shared score-artifact IO for the upload CLIs
factory/                     demo dataset factory (worked example; frozen)
frontend/src/routes/     route table + behavior/pages/ (see frontend/README.md)
docs/                        user-facing; docs/internal/ = maintainer process notes
tests/                       hermetic + plan tier; tests/live/ = opt-in Modal tier
```

## Invariants (do not break)

- **Routes stay sync.** Every handler does blocking IO; FastAPI threadpools
  plain `def` endpoints. Converting them to `async def` reintroduces
  event-loop stalls (see the `backend/api/app.py` docstring).
- **One-place provider registration.** Adding a data source touches only
  `backend/api/providers/<name>.py` + the registry tuple. If a change requires
  editing `trace_source.py` or `scores/` for one provider, put that knowledge
  on the `ProviderSpec` instead.
- **SQL/offline parity.** `backend/api/scores/sql_summaries.py` and
  `scores/offline.py` compute the same summary shapes in SQL and Python.
  Change both together (shapes pinned by `tests/test_scores_io.py`).
- **Env vars go through `backend.paths.env_value`** and every
  `PERSONA_AUDIT_*` literal must appear in `.env.example` (enforced by
  `tests/test_hygiene.py`).
- **`backend/` never imports `factory/`** (enforced by
  `tests/test_workflow_builders.py`).
- **Do not vendor xenon.** Import `pipelines_v2.api` and (in workflow files
  only) `papers.voice.*` directly; the serving layer goes through
  `backend/api/paper_assets.py`. Update the pinned Git ref only after the
  xenon commit is pushed.
- **Never run `pytest -m modal_live` unprompted** — it spends real GPU money.
  Plan-tier tests (`tests/test_workflow_plans.py`) are the free contract check.
- **Historical run ids are data, not config.** Constants like
  `wr_667d470028fd_c294c37f` and `behavior_audit_*` artifact roots name
  existing shipped artifacts; renaming them breaks fixture resolution.
- Keep API routes stable (`tests/test_hygiene.py` pins the inventory) and
  `docs/adapter-contract.md` aligned with `backend/api/models.py`.
- Never print `.env` values; `.env` stays untracked.

## Modal Workflows

All GPU work runs on Modal through xenon's `pipelines_v2`, always via the
wrapper (never the xenon CLI directly from this repo, never local ad hoc
generation):

```bash
backend/scripts/run_xenon_workflow.sh plan --file backend/workflows/tau2_scoring.py
backend/scripts/run_xenon_workflow.sh run  --file backend/workflows/tau2_scoring.py --logging INFO
```

`plan` is free (static preflight). `docs/xenon-modal-runbook.md` is the
canonical operating guide; `docs/add-a-scoring-space.md` covers bringing new
probes / vector spaces / external scores into the audit; `backend/scripts/bootstrap_modal.py --check`
verifies the account is set up.

## Debugging an empty dashboard

1. `curl http://localhost:8100/api/health` — it reports the resolved provider,
   trace source + count, and score source.
2. `GET /api/audit/report?provider=<provider>` — confirm traces before
   touching frontend code; confirm scores before touching chart logic.
3. New data not showing? `POST /api/cache/clear`.

## Persona Demo Dataset

The shipped no-database demo: 75 traces (Sol / Marrow / control over 25
seeds) with real activation scores, registered as the `persona_demo`
provider. Only `data/demo/normalized_traces.json` and its score cache in
`data/supplemental_scores/` are tracked. It was built by the `factory/`
pipeline (see `factory/README.md`); factory outputs under `artifacts/` and
`data/demo/stage*/` are gitignored.

## Verify

```bash
uv run pytest
uv run ruff check . && uv run ruff format --check .
backend/scripts/run_xenon_workflow.sh plan --file backend/workflows/tau2_scoring.py
cd frontend && npm run build
```

Quick trace-loading smoke:

```bash
uv run python -c "from backend.api.trace_source import load_product_traces; t, p, s = load_product_traces(); print(len(t), p, s)"
```
