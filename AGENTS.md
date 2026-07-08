# Agent Notes

## Repo Map

```text
backend/    FastAPI backend, loaders, workflows, upload scripts
frontend/   React dashboard
data/       bundled score caches
reports/    bundled report artifacts
tests/      backend tests
docs/       public setup, adapter, and release-prep docs
```

This repo depends on Xenon through the pinned Git dependency in `pyproject.toml`.

Use Xenon imports directly:

```python
from pipelines_v2.api import ...
from papers.voice.assistant_axis.assets import ...
from papers.voice.emotions.assets import ...
```

Do not vendor Xenon code here. Update the Git dependency ref only after the target Xenon commit is pushed and installable.

## First Checks

```bash
git status --short --branch
test -f .env && sed -n 's/^\([^#=][^=]*\)=.*/\1/p' .env | sort
```

Never print `.env` values.

## Run

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

## Data

- `.env` is local only. Never commit it.
- `BEHAVIOR_AUDIT_DATABASE_URL` is the public Postgres-compatible database URL.
- `XENON_NEON_DATABASE_URL` remains a legacy compatibility alias.
- Missing `.env` means local caches and smoke data only.
- Full Tau2 source files are external.
- `frontend/dist/` is intentionally tracked as the bundled dashboard build.
- `frontend/node_modules/` and generated caches stay ignored/local.
- If the UI shows no live data, check `.env` first.

Use `.env.example` for the supported runtime, table, score, and workflow env vars.
Use `docs/adapter-contract.md` for the normalized public trace shape.
Use `docs/agent-quickstart.md` for coding-agent operating context.

## Modal Workflows (Generation + Scoring)

All GPU work (demo generation, activation scoring) runs on Modal through
Xenon's `pipelines_v2`. Use the wrapper — do not invoke the Xenon CLI directly
from this repo, and do not use local Ollama or ad hoc generation:

```bash
backend/scripts/run_xenon_workflow.sh plan --file backend/workflows/demo_generation.py
backend/scripts/run_xenon_workflow.sh run  --file backend/workflows/demo_generation.py --logging INFO
```

`docs/xenon-modal-runbook.md` is the canonical reference: workflow contract,
efficiency rules, recovery commands, and troubleshooting.

## Key Files

- `backend/api/app.py`: FastAPI routes
- `backend/api/trace_source.py`: Postgres/local trace loading
- `backend/api/neon_scores.py`: score loading and cache fallback
- `backend/paths.py`: repo paths and `.env` loading
- `backend/workflows/common.py`: shared Modal config for all workflows
- `backend/workflows/tau2_scoring.py`: Tau2 scoring workflow
- `backend/workflows/hermes_scoring.py`: Hermes scoring workflow
- `backend/workflows/demo_generation.py`: demo dataset generation workflow (round-based)
- `backend/workflows/demo_scoring.py`: scoring surfaces over normalized demo traces
- `backend/demo/`: demo dataset machinery (personas, seeds, QA, separation metrics)
- `backend/scripts/demo_hillclimb.py`: demo hill-climb driver (docs/demo-hillclimb.md)
- `docs/demo-monitoring-plan.md`: autonomous hill-climb loop (`demo_hillclimb tick` + escalator)
- `backend/scripts/run_xenon_workflow.sh`: run any workflow on Modal via Xenon
- `docs/xenon-modal-runbook.md`: canonical Modal/Xenon operating guide

## Verify

```bash
uv run pytest
uv run python -m py_compile backend/api/app.py backend/workflows/*.py backend/demo/*.py backend/scripts/demo_hillclimb.py
backend/scripts/run_xenon_workflow.sh plan --file backend/workflows/tau2_scoring.py
backend/scripts/run_xenon_workflow.sh plan --file backend/workflows/hermes_scoring.py
backend/scripts/run_xenon_workflow.sh plan --file backend/workflows/demo_generation.py
cd frontend && npm run build
```

Quick database/local smoke:

```bash
uv run python -c "from backend.api.trace_source import load_product_traces; traces, provider, source = load_product_traces(); print(len(traces), provider, source)"
```
