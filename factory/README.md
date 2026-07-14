# Demo Dataset Factory

This directory is the worked example that built the shipped persona-demo
dataset (`data/demo/normalized_traces.json` plus its score cache in
`data/supplemental_scores/`). It is **not** part of the product runtime —
`backend/` never imports `factory/` (enforced by a test) — but it is kept in
the repo as a template for building your own contrastive, scored dataset.

## What it does

An autonomous "hill-climb" loop generated three-persona conversations and
iterated on the persona prompts until activation scores separated the tracks:

```text
generate (Modal GPU)   factory/workflows/demo_generation.py — one round of
                       assistant replies for every seed x track (Sol / Marrow /
                       control), one Modal run per conversation turn
qa (local)             factory/hillclimb/transcript_qa.py — lexical persona
                       checks (contrast, forbidden phrasing, question rate)
normalize (local)      factory/hillclimb/normalize.py — histories -> AuditTrace
                       rows with paired-track labels
score (Modal GPU+CPU)  factory/workflows/demo_scoring.py — the product's tau2
                       scoring steps over the demo traces
evaluate (local)       factory/hillclimb/separation.py — paired Cohen's d per
                       score surface with a response-length confound guard;
                       gates decide advance / iterate / escalate
```

The driver is `factory/scripts/demo_hillclimb.py` (`tick` runs one decision
cycle; `run-iteration` runs the whole pipeline once). State, round files, QA
reports, and pulled Modal artifacts live under the gitignored
`artifacts/demo_hillclimb/`. Stage gates and the decision table are in
`factory/hillclimb/checkin.py`; persona prompt versions in
`factory/hillclimb/personas.py`.

The loop is frozen: Stage 2 passed, the prompts are locked, and the winning
dataset was promoted to `data/demo/`. Internal planning docs are under
`docs/internal/`.

## Running a round yourself

Requires Modal auth, an `HF_TOKEN` secret, and the model on your model volume
(`uv run python -m backend.scripts.bootstrap_modal` sets all of that up), plus
a sibling xenon checkout for the wrapper:

```bash
backend/scripts/run_xenon_workflow.sh plan --file factory/workflows/demo_generation.py
uv run python -m factory.scripts.demo_hillclimb run-iteration
```

## Regenerating the shipped score cache

`factory/scripts/build_demo_score_cache.py` rebuilds
`data/supplemental_scores/<run_id>_assistant_trait_scores.json` from the
scoring artifacts cached under `artifacts/demo_hillclimb/modal_cache/`. That
cache directory is gitignored: a fresh clone cannot rebuild the shipped file
without re-running `factory/workflows/demo_scoring.py` on Modal first (the
shipped cache itself is tracked, so this only matters if you want to reproduce
or replace it).
