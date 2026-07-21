# Hermes Demo Dataset

The bundled fallback for the `hermes` provider: 30 real hermes-agent
trajectories (multi-turn tool calling with reasoning blocks) sampled from the
Apache-2.0 Hugging Face dataset
[`lambda/hermes-agent-reasoning-traces`](https://huggingface.co/datasets/lambda/hermes-agent-reasoning-traces)
(config `kimi`) and normalized into `AuditTrace` JSON. It renders whenever no
real Hermes `state.db` is found (see `backend/adapters/hermes/adapter.py` for
the resolution order); override the path with `PERSONA_AUDIT_HERMES_DEMO_TRACES`.

- `normalized_traces.json` — the traces (tracked). Boilerplate system prompts
  are dropped; `<think>` blocks become `AuditTurn.reasoning`; `<tool_call>` /
  `<tool_response>` blocks become tool turns. Dataset category/subcategory map
  onto the product's Source/User dimensions.
- `manifest.json` — the sampled HF row ids (tracked, for reproducibility).
  Trace ids are content-derived from those row ids, so a rebuild against the
  same rows keeps the shipped score cache joined.

Rebuild:

```bash
uv run python -m factory.scripts.build_hermes_demo_traces
```

Scores for this dataset ship as
`data/supplemental_scores/persona_audit_hermes_demo_v1_assistant_trait_scores.json`,
produced by the standard Hermes scoring workflow
(`backend/workflows/hermes_scoring.py`, run with no state.db present so the
demo is the active source) followed by:

```bash
uv run python -m backend.scripts.upload_hermes_scores \
  --run-id persona_audit_hermes_demo_v1 --skip-neon \
  --local-cache-families assistant_axis,reasoning_assistant_axis \
  --capture-artifact-id ... --projection-artifact-id ... \
  --emotion-artifact-id ... --reasoning-projection-artifact-id ... \
  --reasoning-emotion-artifact-id ...
```
