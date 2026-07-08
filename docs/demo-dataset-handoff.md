# Demo Dataset Handoff

This branch contains the current demo-dataset context for Persona Audit.

## Saved Context

- Build/spec doc: `docs/demo-dataset-build-plan.md`
- One-shot Modal generation smoke workflow: `backend/workflows/demo_generation.py`
- Branch: `codex/demo-dataset-spec`
- Spec commit: `ea530d0 Document demo dataset build plan`

## What The Demo Is For

The A/B/control dataset is a canned demo that makes Persona Audit legible immediately. It is not the product thesis. The product thesis remains: users bring their own conversation data, score it into activation-derived behavior surfaces, and use the dashboard to inspect patterns, outliers, drift, and failure modes.

## Workflow Path

Use the Xenon/Modal workflow stack. Do not use local Ollama or ad hoc local generation.

Run everything through the wrapper, from this repo:

```bash
backend/scripts/run_xenon_workflow.sh plan --file backend/workflows/demo_generation.py
backend/scripts/run_xenon_workflow.sh run  --file backend/workflows/demo_generation.py --logging INFO
```

The wrapper exists because Xenon's Modal runner mounts `pipelines_v2/` from the
detected workspace root; invoking the CLI directly from this checkout fails
with `local dir .../persona-audit/pipelines_v2 does not exist`. The wrapper
executes from the Xenon checkout (sibling `../xenon`, or `XENON_WORKSPACE_ROOT`)
with `PYTHONPATH` set back to this repo. Full details, efficiency rules, and
troubleshooting: `docs/xenon-modal-runbook.md`.

## Successful Smoke Run

The one-shot Sol generation succeeded through Modal using `meta-llama/Llama-3.3-70B-Instruct`.

- Workflow: `behavior_audit_demo_generation_v1`
- Run ID: `wr_e40080d7a83b_fa787b91`
- Step: `generate_sol_smoke`
- Artifact ID: `generation_run_1_c04aa0ceca81`
- Runtime app: `ap-Nz3gzIlFeWOLVYDrCszZ7Z`
- Artifact path: `/data/artifacts/behavior_audit_demo_generation_v1/generation_run_1_c04aa0ceca81/result.json`

Generated text:

```text
You know what you want: clarity. You want him to be direct. You do not want games. You will tell him that.
```

This validates the core model flow: Persona Audit workflow file -> Xenon `GenerationRunSpec` -> Modal -> Llama 70B -> generation artifact.

## Next Steps

The staged build now runs through the hill-climb structure — see
`docs/demo-hillclimb.md` for the critique of the original plan, the
quantitative Stage 2 gate, and the iteration protocol. In short:

1. `uv run python -m backend.scripts.demo_hillclimb run-iteration --stage 0` and read the transcripts side by side.
2. Iterate prompt versions in `backend/demo/personas.py` per the protocol (one track, one variable per iteration).
3. Stage 1 (5 seeds) iterations include scoring + separation metrics; Stage 2 (25 seeds, needs ESConv) is the freeze gate.
4. Do not scale on transcript-style separation alone; the gate is activation-score separation with length-confounded surfaces excluded.

## Notes

- `xenon` now supports `XENON_WORKSPACE_ROOT` to override workspace-root detection (used for Modal source mounts); once the pin in `pyproject.toml` includes that commit, workflows can run directly from this repo's venv. No other xenon edits should be needed for this stage.
- `persona-audit` should own the demo workflow and final public demo artifacts.
- Generated public demo data should be fixed and shipped; users do not need to recreate the generation run.
- If using ESConv seeds, document the `cc-by-nc-4.0` license/provenance.
