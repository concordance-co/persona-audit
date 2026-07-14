# Persona Audit

Persona Audit is a FastAPI backend plus React dashboard for inspecting LLM
conversation behavior: persona traits, emotion posture, outlier turns,
sessions, users/cohorts, and scoring coverage. Scores come from residual-stream
activations captured on Modal via [xenon](https://github.com/concordance-co/xenon)
`pipelines_v2`; a bundled, pre-scored demo dataset means none of that is
required just to try it.

> **Built on xenon.** This project is a downstream application of
> [xenon](https://github.com/concordance-co/xenon): all activation capture,
> vector spaces, and Modal orchestration come from xenon's `pipelines_v2` and
> `papers.voice` packages, installed automatically as a pinned Git dependency
> (`pyproject.toml`). You need nothing extra to run the dashboard. To run
> scoring workflows you additionally need a local xenon clone next to this
> repo (its source is mounted into the Modal runner) — see
> [Scoring on your own Modal account](#scoring-on-your-own-modal-account).
> This repo never vendors or forks xenon code.

## Quickstart (no database, no GPU)

```bash
uv sync
uv run uvicorn backend.api.app:app --reload --port 8100
```

```bash
cd frontend && npm install && npm run dev
```

Open `http://localhost:5173` and pick **Persona demo** in the sidebar: 75
bundled traces (the same 25 conversations answered by two personas and a
control) with real activation scores. `curl http://localhost:8100/api/health`
self-diagnoses which trace/score source is active.

## Layout

```text
backend/api/        FastAPI serving layer (registry, providers, scores, view models)
backend/adapters/   source-specific trace adapters (e.g. Hermes state.db)
backend/workflows/  Modal scoring workflows (tau2, hermes) + shared config
backend/scripts/    Modal wrapper, bootstrap, upload CLIs
factory/            the demo dataset factory (worked example; not product runtime)
frontend/           React dashboard (Vite; map in frontend/README.md)
data/, reports/     bundled public-safe fixtures
docs/               user-facing docs (docs/internal/ = maintainer process notes)
tests/              hermetic tests + free plan tier + opt-in live Modal tier
```

## Requirements

- Python 3.13+, [`uv`](https://docs.astral.sh/uv/)
- Node.js 20+
- [xenon](https://github.com/concordance-co/xenon) — installed automatically
  by `uv sync` from the Git pin; a sibling clone is needed only for running
  scoring workflows on Modal
- Optional: Postgres (live trace/score tables), Modal + `HF_TOKEN` (scoring)

Xenon installs automatically from the pinned Git dependency in
`pyproject.toml`. Update that pin only after the target xenon commit is pushed.

## Configuration

Copy `.env.example` to `.env` and fill only what you need. Every setting uses
the `PERSONA_AUDIT_*` prefix; the older `BEHAVIOR_AUDIT_*` spellings (and
`XENON_NEON_DATABASE_URL` for the database URL) still work as deprecated
aliases with a warning.

Database (optional — the demo needs none):

```bash
PERSONA_AUDIT_DATABASE_URL=postgresql://persona:persona@localhost:5432/persona_audit
docker compose up -d postgres   # dev-only local Postgres with those credentials
```

Set `PERSONA_AUDIT_TRACE_SOURCE=local` to force local loaders and skip the
database entirely. Databases created before the `persona_audit_*` table rename
can either be re-uploaded or pointed at via the table env vars (e.g.
`PERSONA_AUDIT_TRACE_TABLE=behavior_audit_traces`).

## Bring Your Own Data

The stable contract is the normalized trace shape (`AuditTrace`/`AuditTurn`,
see [docs/adapter-contract.md](docs/adapter-contract.md)) plus a one-module
provider registration:

1. Convert your conversations into the normalized shape
   ([docs/llm-data-conversion-instructions.md](docs/llm-data-conversion-instructions.md)
   is a ready-made instruction template for a coding agent).
2. Register a provider: one module under `backend/api/providers/` exposing a
   `SPEC`, plus one entry in `backend/api/providers/__init__.py`. The
   `persona_demo` provider is the smallest worked example.
3. Optionally upload normalized rows to Postgres
   (`uv run python -m backend.scripts.upload_local_data`) and run scoring.
4. Open the dashboard with `?provider=<your-key>`.

There is intentionally no universal importer — source data varies too much;
the normalized shape is the boundary.

The fastest route is to hand the whole job to a coding agent. Paste this:

```text
I have conversation data at <PATH/DESCRIPTION OF MY DATA> that I want to
browse in Persona Audit. Read docs/adapter-contract.md and
docs/llm-data-conversion-instructions.md in this repo, then convert my data
into the normalized trace shape and register it as a provider (one module
under backend/api/providers/ plus one registry entry — persona_demo is the
smallest example). Follow the "Required Response From The Coding Agent"
section of the instructions doc, add focused tests, and finish by showing me
the command to open the dashboard on my data.
```

(The dashboard's in-app help has the same prompt cards under "Run On My Data".)

## Scoring on your own Modal account

Scoring captures Llama-3.3-70B residual activations and projects them onto
released trait/emotion vector spaces. One-time setup:

```bash
modal setup                                          # authenticate
git clone https://github.com/concordance-co/xenon ../xenon   # source mount for the runner
uv run python -m backend.scripts.bootstrap_modal     # volumes + HF secret + model download
```

The bootstrap is idempotent and `--check` verifies without creating anything.
Then plan (free, no GPU) and run through the wrapper:

```bash
backend/scripts/run_xenon_workflow.sh plan --file backend/workflows/tau2_scoring.py
backend/scripts/run_xenon_workflow.sh run  --file backend/workflows/tau2_scoring.py --logging INFO
```

Upload results with `backend/scripts/upload_tau2_scores.py` /
`upload_hermes_scores.py` (they create tables as needed), or build local score
caches. [docs/xenon-modal-runbook.md](docs/xenon-modal-runbook.md) covers the
workflow contract, efficiency rules, and recovery commands. The
`PERSONA_AUDIT_MODEL_ID` and layer choices are documented in
`backend/workflows/common.py` — the released vector spaces are precomputed
against the 70B, so changing the model changes the science, not just the cost.

To bring your own probes, vector spaces, or externally computed scores into
the audit, see [docs/add-a-scoring-space.md](docs/add-a-scoring-space.md).

`factory/` contains the full pipeline that generated and score-validated the
bundled demo dataset — a worked example for building your own contrastive
dataset (see [factory/README.md](factory/README.md)).

## Tests

| Tier | Command | Needs | Cost |
| --- | --- | --- | --- |
| Hermetic (default) | `uv run pytest` | nothing | free, ~3s |
| Plan contract | included in the default run (`tests/test_workflow_plans.py`) | nothing — static xenon preflight | free |
| Live Modal | `PERSONA_AUDIT_LIVE_TESTS=1 uv run pytest -m modal_live` | Modal auth, bootstrap complete | **real GPU money** (~$5–20/session) |

The live tier really executes scoring (70B capture over 3 demo traces) and
generation (1 seed x 3 personas) on Modal and validates the returned score
rows end-to-end. It is double-gated (explicit marker + env var), never runs in
push/PR CI, and can be dispatched manually via the `modal-live` GitHub Actions
workflow.

## Verify

```bash
uv run pytest
uv run ruff check . && uv run ruff format --check .
cd frontend && npm run build
```

After uploading new data, `POST /api/cache/clear` (or restart) so the memoized
report views pick it up.

## Privacy

Do not commit `.env`, local Hermes state, generated score caches, Modal
artifacts, or private source data — `.gitignore` already quarantines them. Run
[docs/release-checklist.md](docs/release-checklist.md) before publishing a
fork with your own data.
