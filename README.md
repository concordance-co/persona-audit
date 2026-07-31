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
- Node.js 22.22+
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
see [docs/adapter-contract.md](docs/adapter-contract.md)). JSON arrays and
JSONL are both accepted. The shortest path needs no Python changes:

1. Convert your conversations into the normalized shape
   ([docs/llm-data-conversion-instructions.md](docs/llm-data-conversion-instructions.md)
   is a ready-made instruction template for a coding agent).
2. Validate them:
   `uv run python -m backend.scripts.validate_traces /path/to/traces.jsonl`.
3. Set `PERSONA_AUDIT_LOCAL_TRACES=/absolute/path/to/traces.jsonl`; optionally
   set `PERSONA_AUDIT_LOCAL_PROVIDER_ID` and `PERSONA_AUDIT_LOCAL_LABEL`.
4. Open the dashboard with `?provider=local`.
5. Optionally score the file on your Modal account using the database-free
   path below. Postgres is only an optional additional sink.

For source-specific parsing, custom dimensions, or deployment-specific
behavior, register a provider module under `backend/api/providers/` exposing a
`SPEC`, plus one entry in `backend/api/providers/__init__.py`. The
`persona_demo` provider is the smallest worked example. Registered providers
are discovered dynamically by the dashboard.

The Hermes loader and scoring workflow remain available as an optional
integration, but Hermes is intentionally hidden from the public provider
selector. Set `features.show_in_provider_selector` to `true` in
`backend/api/providers/hermes.py` when developing that integration.

The fastest route is to hand the whole job to a coding agent. Paste this:

```text
I have conversation data at <PATH/DESCRIPTION OF MY DATA> that I want to
browse in Persona Audit. Read docs/adapter-contract.md and
docs/llm-data-conversion-instructions.md in this repo, convert my data into
validated normalized JSONL, and use the zero-code local provider unless the
source needs a reusable custom adapter. Follow the "Required Response From The
Coding Agent" section, add focused tests for any adapter code, and finish by
showing me the command to open the dashboard on my data.
```

(The dashboard's in-app help has the same prompt cards under "Run On My Data".)

## Scoring on your own Modal account

Scoring captures Llama-3.3-70B residual activations and projects them onto
released trait/emotion vector spaces. One-time setup:

```bash
uv run modal setup
git clone https://github.com/concordance-co/xenon ../xenon
uv run modal secret create huggingface HF_TOKEN=YOUR_HUGGING_FACE_TOKEN
uv run python -m backend.scripts.bootstrap_modal
```

The Hugging Face account must have accepted the Llama-3.3-70B license.
`bootstrap_modal` creates the model/data volumes, downloads the model through
that secret, and verifies the sibling Xenon checkout. It is idempotent;
`--check` verifies without creating or downloading anything.

To score normalized local data, use an absolute trace path, plan for free,
then run:

```bash
export PERSONA_AUDIT_LOCAL_TRACES=/absolute/path/to/traces.jsonl
backend/scripts/run_xenon_workflow.sh plan --file backend/workflows/local_scoring.py
backend/scripts/run_xenon_workflow.sh run --file backend/workflows/local_scoring.py --logging INFO
```

The run result identifies the `capture_local`, `score_assistant_axis`, and
`score_emotions` artifacts. Materialize them into the dashboard's local,
gitignored score cache:

```bash
uv run python -m backend.scripts.upload_tau2_scores \
  --provider local \
  --workflow-name persona_audit_local_scoring_v1 \
  --artifact-root /data/artifacts/persona_audit_local_scoring_v1 \
  --run-id <wr_...> \
  --capture-artifact-id <capture_local artifact id> \
  --projection-artifact-id <score_assistant_axis artifact id> \
  --emotion-artifact-id <score_emotions artifact id> \
  --no-high-stakes \
  --skip-database
```

The importer writes
`data/supplemental_scores/<run-id>_assistant_trait_scores.json.gz`. Set the
printed `PERSONA_AUDIT_LOCAL_SCORE_RUN_ID=<run-id>` in `.env`, restart the API
or `POST /api/cache/clear`, and open `?provider=local`. No database is involved.
Set `PERSONA_AUDIT_SCORE_CACHE_DIR` to an absolute directory if the cache
should live outside the repo; the importer and API both honor it.
If `PERSONA_AUDIT_DATABASE_URL` is configured and `--skip-database` is omitted,
the same command writes both the local cache and Postgres tables.

The importer name is historical; its provider and artifact arguments are
generic. [docs/xenon-modal-runbook.md](docs/xenon-modal-runbook.md) covers the
workflow contract, efficiency rules, artifact discovery, and recovery
commands. The
`PERSONA_AUDIT_MODEL_ID` and layer choices are documented in
`backend/workflows/common.py` — the released vector spaces are precomputed
against the 70B, so changing the model changes the science, not just the cost.

To bring your own probes, vector spaces, or externally computed scores into
the audit, see [docs/add-a-scoring-space.md](docs/add-a-scoring-space.md).
To compose existing payloads into different pages, see
[docs/remix-a-view.md](docs/remix-a-view.md).

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
