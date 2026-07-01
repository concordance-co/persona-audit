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

Because `persona-audit` consumes Xenon as a Git dependency, running Modal workflows from the `persona-audit` checkout can fail with:

```text
local dir .../persona-audit/pipelines_v2 does not exist
```

The working path is to run the `persona-audit` workflow file from the Xenon checkout so Modal mounts Xenon's real `pipelines_v2` source:

```bash
cd /Users/marshallvyletel/repos/concordance/xenon
PYTHONPATH=/Users/marshallvyletel/repos/concordance/persona-audit   uv run python -m pipelines_v2.cli workflow plan   --file /Users/marshallvyletel/repos/concordance/persona-audit/backend/workflows/demo_generation.py

PYTHONPATH=/Users/marshallvyletel/repos/concordance/persona-audit   uv run python -m pipelines_v2.cli workflow run   --file /Users/marshallvyletel/repos/concordance/persona-audit/backend/workflows/demo_generation.py   --logging INFO
```

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

1. Expand `backend/workflows/demo_generation.py` from one Sol example to Stage 0 with Sol, Marrow, and control for one seed.
2. Keep using Llama 3.3 70B and identical generation params across tracks.
3. Convert generation artifacts into normalized `AuditTrace` rows with metadata: `provider_id`, `seed_id`, `paired_group_id`, `track`, `persona_prompt_id`, `source_dataset`, `sensitivity_tier`, `decision_type`, `generation_model`, `generation_params`, and `public_provenance`.
4. Run Stage 1 over five seeds only after Stage 0 transcripts are clearly distinct.
5. Run Stage 2 scoring through the existing capture/projection workflow before scaling.
6. Do not scale based only on transcript length/lexicon. Stage 2 passes when activation-derived Persona Audit surfaces separate Sol, Marrow, and control in useful, inspectable ways.

## Notes

- `xenon` should not need edits for this stage.
- `persona-audit` should own the demo workflow and final public demo artifacts.
- Generated public demo data should be fixed and shipped; users do not need to recreate the generation run.
- If using ESConv seeds, document the `cc-by-nc-4.0` license/provenance.
