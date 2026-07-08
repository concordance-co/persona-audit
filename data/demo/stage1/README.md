# Demo dataset snapshot: stage1

Frozen 2026-07-08T12:01:43+00:00 from stage 1, iteration 3.

- Separation gate: PASS (objective 5.845)
- Transcript QA: PASS
- Prompts: control=control_v1, marrow=marrow_v2, sol=sol_v1

First fully-passing dataset: Stage 1, 5 seeds x 3 tracks, marrow_v2. Both separation and QA gates green (iteration 3). Fallback point before Stage 2 seed curation.

`normalized_traces.json` is the shippable dataset (AuditTrace rows). `manifest.json` carries the exact prompt texts and gate results. Regenerate with `demo_hillclimb run-iteration`; see docs/demo-hillclimb.md.
