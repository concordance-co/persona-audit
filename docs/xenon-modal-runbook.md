# Xenon Modal Runbook

How to run Persona Audit's GPU work — demo-data generation and activation
scoring — through Xenon's `pipelines_v2` Modal backend. This is the canonical
reference for coding agents; prefer these commands over ad hoc invocations.

## TL;DR

All Modal workflows in this repo run through one wrapper:

```bash
# Validate a workflow (no GPU, no Modal spend)
backend/scripts/run_xenon_workflow.sh plan --file factory/workflows/demo_generation.py

# Run it (Modal, GPU)
backend/scripts/run_xenon_workflow.sh run --file factory/workflows/demo_generation.py --logging INFO

# Discover / inspect / recover runs
backend/scripts/run_xenon_workflow.sh runs --file factory/workflows/demo_generation.py
backend/scripts/run_xenon_workflow.sh show --run-id wr_...
backend/scripts/run_xenon_workflow.sh resume --file factory/workflows/demo_generation.py --latest-failed
backend/scripts/run_xenon_workflow.sh rerun-step --file backend/workflows/tau2_scoring.py --run-id wr_... --step report
```

Always `plan` before `run`. Plan is free and catches spec errors; run costs
GPU time.

The workflows:

| Workflow file | Purpose | GPU runner |
| --- | --- | --- |
| `factory/workflows/demo_generation.py` | Demo dataset generation, one round per run (Sol/Marrow/control) | `generation_gpu` |
| `factory/workflows/demo_scoring.py` | Product scoring surfaces over normalized demo traces | `capture_gpu` |
| `backend/workflows/tau2_scoring.py` | Tau2 trace scoring (capture + projections + emotions + probes) | `capture_gpu` |
| `backend/workflows/hermes_scoring.py` | Hermes trace scoring (capture + projections + emotions) | `capture_gpu` |

Shared Modal config (model volume, caches, secrets, env parsing) lives in
`backend/workflows/common.py`; compose it rather than repeating runner
boilerplate, and keep the invariants in `tests/test_workflow_builders.py`
green. For the demo dataset loop specifically, don't call these workflows by
hand — drive them with `factory/scripts/demo_hillclimb.py`
(see docs/internal/demo-hillclimb.md).

## Why The Wrapper Exists

Xenon's Modal runner mounts `pipelines_v2/` (and `papers/`) into the container
from the **detected workspace root**. Detection walks the `pipelines_v2` module
path and cwd looking for `pyproject.toml`/`.git`. Because this repo installs
Xenon non-editable from Git, detection lands on the persona-audit repo root —
which has no `pipelines_v2/` directory — and Modal fails with:

```text
local dir .../persona-audit/pipelines_v2 does not exist
```

The wrapper fixes this by executing the CLI from the Xenon checkout (default:
the sibling `../xenon`, override with `XENON_WORKSPACE_ROOT` in env or `.env`)
with `PYTHONPATH` pointing back at this repo so `backend.*` imports resolve. It
also absolutizes repo-relative `--file` paths, so you can pass paths exactly as
they appear in this repo.

Xenon also supports `XENON_WORKSPACE_ROOT` directly (honored in
`pipelines_v2.core.paths.find_workspace_root`, included in the pinned ref), so
workflows can run straight from this repo's venv:

```bash
XENON_WORKSPACE_ROOT=../xenon uv run python -m pipelines_v2.cli workflow run \
  --file factory/workflows/demo_generation.py --logging INFO
```

Both forms are supported; the wrapper stays the default because it also works
if the pin lags the checkout and it keeps one canonical command in docs.

Keep the local Xenon checkout on (or compatible with) the commit pinned in
`pyproject.toml` — the wrapper executes the checkout's `pipelines_v2`, and
Modal mounts that same source remotely.

## Workflow File Contract

The Xenon CLI loads a workflow file and calls three functions:

- `build_dataset() -> Dataset` — the examples (prompts + labels + metadata)
- `build_workflow(dataset) -> WorkflowSpec` — named steps, each bound to a
  runner name and a spec (`GenerationRunSpec`, `CaptureSpec`, `ProjectionSpec`, …)
- `build_runner_specs() -> dict[str, RunnerSpec]` — maps runner names to
  `ModalRunnerSpec`/`LocalRunnerSpec` with resources, volumes, secrets

Run state is mirrored to `~/.xenon/pipelines_v2/catalog`. Structured progress
and Modal app ids print to stderr with `--logging INFO`; the JSON result stays
on stdout.

## Efficiency Rules

These keep Modal runs fast and cheap. The workflows in this repo already
follow them; preserve the pattern when extending.

1. **One run, many examples.** Never loop `workflow run` over examples. Put
   all examples for a stage into `build_dataset()`; vLLM batches them inside
   one engine session. Batch size is governed by `max_num_seqs`
   (`PERSONA_AUDIT_DEMO_GENERATION_MAX_NUM_SEQS`, default 16).
2. **Workflow batching stays on.** `ModalResources(enable_workflow_batching=True)`
   lets Xenon coalesce compatible ready steps into one Modal call with one
   loaded model. Without it every step cold-starts its own container. All
   Modal runners in this repo (GPU and CPU) set it.
3. **Caches live on persistent volumes.** Model weights load from the
   model volume at `/models` (`model_path_root`, no HF download), and
   `HF_HOME` / `VLLM_CACHE_ROOT` / `TORCHINDUCTOR_CACHE_DIR` point at the same
   volume with `commit_on_success=True`. Don't remove these; they're the
   difference between a warm start and re-downloading a 70B model.
4. **Recover, don't rerun.** A failed run resumes with
   `resume --latest-failed`, reusing completed step artifacts. A changed step
   reruns with `rerun-step` / `rerun-from-step`. A full rerun repays every GPU
   minute already spent.
5. **Prefix caching is on for generation and plain residual capture.** Note
   Xenon rejects it for MoE-routing capture and patched generation; that
   doesn't apply to these workflows today.
6. **Tune with env vars, not edits.** GPU type, timeouts, vLLM knobs, and
   dataset limits are env-overridable — see `.env.example`
   (`PERSONA_AUDIT_DEMO_GENERATION_*`, `PERSONA_AUDIT_TAU2_*`,
   `PERSONA_AUDIT_HERMES_*`).

## Generation (Demo Dataset)

`factory/workflows/demo_generation.py` implements the flow in
`docs/internal/demo-dataset-build-plan.md`: fixed user turns, three system-prompt
tracks (`sol`, `marrow`, `control`), identical decoding params, Llama 3.3 70B
via `GenerationRunSpec` on `H100:2`.

The workflow generates **one round** (assistant turn t for every seed x track,
batched into one vLLM session) per run. The driver
`factory/scripts/demo_hillclimb.py generate` builds each round's examples from
`factory/hillclimb/` (personas, seeds, per-track histories), writes a round file,
and points `PERSONA_AUDIT_DEMO_ROUND_FILE` at it; without that env var the
workflow builds the Stage 0 turn-0 smoke examples. Scaling stages scales the
**dataset per round**, never the number of workflow runs per round.

Results land as `result.json` under
`/data/artifacts/persona_audit_demo_generation_v1/<artifact_id>/` on the
configured Modal data volume; the driver pulls them via `ModalVolumeStore` into
`artifacts/demo_hillclimb/`.

## Scoring

`tau2_scoring.py` / `hermes_scoring.py` run the capture → score pipeline:

1. `capture_*` (GPU): one `CaptureSpec` capturing pooled residuals at the
   assistant/emotion/high-stakes layers.
2. `analysis_cpu` steps: projections onto trait coordinates, emotion vector
   space scores, persisted-probe inference. These are many small independent
   steps; workflow batching folds them into few Modal calls.
3. Score artifacts are pulled and uploaded with
   `backend/scripts/upload_tau2_scores.py` /
   `upload_hermes_scores.py`, which read `result.json` from the
   configured data volume and write the `persona_audit_*_score_*` tables.

For the demo dataset, `factory/workflows/demo_scoring.py` reuses the Tau2
workflow's exact steps and surfaces over the normalized demo traces
(`artifacts/demo_hillclimb/normalized_traces.json`, override with
`PERSONA_AUDIT_DEMO_TRACES_FILE`), carrying `track`/`paired_group_id` labels
through to the score artifacts for the separation metrics in
`factory/hillclimb/separation.py`.

## Troubleshooting

- **`local dir .../pipelines_v2 does not exist`** — you invoked the CLI
  directly from this repo. Use the wrapper (or set `XENON_WORKSPACE_ROOT` once
  the Xenon pin includes it).
- **`ModuleNotFoundError: backend`** — the CLI ran without this repo on
  `PYTHONPATH`. Use the wrapper.
- **HF auth errors on Modal** — the runners need the `HF_TOKEN` env var
  locally (Xenon forwards it as a Modal secret).
- **`TransferPolicyError` on artifact download** — large artifact pulls
  require `TransferPolicy(allow_large_transfer=True)`, already set on this
  repo's `ModalVolumeStore`s.
- **Slow first run, fast later** — expected: the first run populates model
  weights/compile caches on the volume. Caches commit only on step success.
- **Long jobs** — always pass `--logging INFO`; the Modal app id printed to
  stderr lets you follow the run in the Modal dashboard.
