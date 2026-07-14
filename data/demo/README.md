# Persona demo dataset

A small, self-contained dataset that makes Persona Audit legible on first run:
the same user conversations answered by three assistant personas, so the audit
surfaces show clear persona separation.

- **Sol** — declarative and decisive; says the plain thing.
- **Marrow** — hedging and exploratory; slows things down, ends on a question.
- **control** — a plain "You are a helpful assistant." baseline.

25 seed conversations × 3 personas = **75 traces**, scored on the assistant-trait
and high-stakes surfaces. Both separation gates pass (paired Cohen's d objective
≈ 4.4; transcript QA clean). Seeds span sensitivity tiers 0–2 across 25 decision
types and are authored in-house (modeled on ESConv-style support conversations,
no cc-by-nc-4.0 text reproduced — the dataset is MIT-clean).

## What ships here

Only the two files the dashboard reads are tracked:

| File | What it is |
| --- | --- |
| `data/demo/normalized_traces.json` | The 75 traces (normalized `AuditTrace` rows). |
| `data/supplemental_scores/wr_c325b34b511a_a9ce320d_assistant_trait_scores.json` | Precomputed activation scores (assistant-axis traits + high-stakes probes). |

The hill-climb "factory" — stage snapshots, transcripts, separation/QA reports,
generation state — is intentionally gitignored (`data/demo/stage*/`). You don't
need it to load or view the demo.

## How to load it in the dashboard

No database required. From the repo root:

```bash
uv run uvicorn backend.api.app:app --port 8100     # terminal 1: API
cd frontend && npm run dev                          # terminal 2: UI
```

Open <http://localhost:5173>, choose **Persona demo** in the sidebar. The
Overview leads with a Track-by-Persona trait matrix (Sol vs Marrow vs control);
Sessions can be filtered to a single persona; each session shows the
conversation with every assistant turn scored.

The provider is registered as `persona_demo` (`backend/api/providers/persona_demo.py`); the
loader reads the file above (`backend/api/trace_source.py`), and scores resolve
from the local cache with no Postgres (`backend/api/scores/`). Override
the traces path with `PERSONA_AUDIT_DEMO_PRODUCT_TRACES` if needed.

## Regenerating (maintainers only)

The dataset is produced by the autonomous hill-climb (`docs/internal/demo-hillclimb.md`).
After a Stage 2 run passes, promote the result and rebuild the score cache:

```bash
# 1. run/regenerate the loop (writes the gitignored factory under data/demo/stage2/)
uv run python -m backend.scripts.demo_hillclimb run-iteration --stage 2

# 2. promote the traces to the shipped location
cp data/demo/stage2/normalized_traces.json data/demo/normalized_traces.json

# 3. rebuild the tracked score cache from the cached score artifacts
uv run python -m backend.scripts.build_demo_score_cache
```

If regeneration produces a new scoring run id, update
`DEFAULT_RUN_ID` in `backend/api/providers/persona_demo.py` and the tracked
filename to match, and add it to the `.gitignore` allowlist.
