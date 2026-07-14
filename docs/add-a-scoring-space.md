# Add a Scoring Space

How to bring new mech-interp findings — a trained probe, a precomputed vector
space, or scores computed anywhere else — into the audit. Three routes, from
most to least turnkey.

Shared vocabulary: every score row carries a `score_family` (which space it
belongs to) and a `coordinate` (the direction/probe within that space). The
canonical row shape is `SCORE_COLUMNS` in `backend/scores_io.py`.

## Route A: a persisted probe (trained in xenon)

For probes exported with xenon's persisted-probe format (a `result.json`
payload from `PersistedProbeImportSpec`-compatible training).

1. Put the probe artifact on your Modal data volume
   (`PERSONA_AUDIT_DATA_VOLUME`), e.g. under `/data/artifacts/my_probes_v1/<artifact_id>/result.json`.
   `modal volume put <volume> <local_dir> /data/artifacts/my_probes_v1/<artifact_id>` works.
2. Append an entry to `HIGH_STAKES_PERSISTED_PROBES` in
   `backend/api/scoring_spaces.py` with your `domain`, `probe_family`,
   `artifact_id`, `target_root`, and metrics. That single config entry drives:
   - the workflow steps (`backend/workflows/common.py:high_stakes_probe_steps`
     generates an import + inference step per entry), and
   - the public readiness payload (internal ids are stripped automatically by
     `public_probe_summaries`).
3. Enable probes and run:

   ```bash
   PERSONA_AUDIT_ENABLE_HIGH_STAKES_PROBES=1 \
     backend/scripts/run_xenon_workflow.sh run --file backend/workflows/tau2_scoring.py --logging INFO
   ```

4. Upload the inference artifacts:
   `uv run python -m backend.scripts.upload_tau2_scores --run-id <wr_...> --high-stakes-artifact-id <id> ...`
   (repeat the flag per probe). Rows land with `score_family="high_stakes"`.

Note: probes at a different layer or on full-sequence vs. section features
need a matching `ResidualSite` in the capture step — compare the layer
constants and sites in `backend/workflows/common.py` / `tau2_scoring.py`.

## Route B: a precomputed vector space (xenon asset)

For a new direction set (like the released emotion space) packaged as an
xenon `EmotionPrecomputedVectorSpaceSpec`-compatible artifact.

Copy the emotion pattern — it is four small pieces, all in
`backend/workflows/common.py` and the workflow file:

1. A vector-space step (see `emotion_space_step` / `emotion_vector_space_spec`)
   pointing at your artifact (local path, HF repo, or volume path).
2. A score step (see `emotion_score_step`) projecting a captured feature onto
   it. Reuse an existing capture site if your space targets the same layer;
   otherwise add a `ResidualSite` with your layer to the capture step.
3. Run the workflow, then upload with your own family:
   `backend/scores_io.py` is the library the upload CLIs are built on —
   `load_result(...)` + `score_rows_from_artifact(ArtifactLoad(artifact_id, "<your_family>", payload), ...)`
   + `replace_run(...)` is a complete custom uploader in ~20 lines (see
   `backend/scripts/upload_tau2_scores.py` for the worked example).
4. Remember: the released assistant-axis/emotion spaces are precomputed for
   Llama-3.3-70B at layers 40/52 — a space computed against another model
   needs `PERSONA_AUDIT_MODEL_ID` and its own layer choices.

## Route C: score rows from anywhere (no xenon required)

If you computed scores with your own tooling, you can skip Modal entirely and
bring rows directly. Two equivalent sinks:

- **Local supplemental JSON** (what the bundled demo uses): write
  `data/supplemental_scores/<run_id>_assistant_trait_scores.json` with
  `{"kind": "persona_audit_supplemental_score_rows", "version": 1,
  "run_id": "<run_id>", "rows": [...]}` where each row follows the
  `SCORE_COLUMNS` shape (`run_id`, `score_family`, `coordinate`, `trace_id`,
  `turn_index`, `provider_id`, `score`, ...). Point
  `PERSONA_AUDIT_SCORE_RUN_ID` (or your provider's ScoreConfig) at the run id.
  `factory/scripts/build_demo_score_cache.py` is the worked example.
- **Postgres rows**: `uv run python -m backend.scripts.upload_local_data`
  uploads supplemental JSON files into the score tables, or use
  `backend/scores_io.py` directly.

## Where a new family shows up

Automatically, keyed by `score_family`/`coordinate` (no frontend changes):

- score inventory (`/api/health`, `/api/audit/report` score sections)
- per-session score details and analytics
- tail statistics, histograms, and conversation dynamics in score summaries

The headline pages (Character, Tail explorer, persona vectors) are built on
the assistant-axis and emotion coordinate sets specifically; giving a new
space its own page is a frontend task — see `frontend/README.md` for the map
and how pages consume score payloads.
