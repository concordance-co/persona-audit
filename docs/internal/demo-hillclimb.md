# Demo Dataset Hill-Climb

Automated loop that iterates the Sol/Marrow/control demo dataset until
Persona Audit's activation-derived surfaces separate the tracks. Implements
and extends `docs/internal/demo-dataset-build-plan.md`; read that first.

## Critique Of The Build Plan

The plan is sound about what to build (paired A/B/control tracks, staged
scale-up, activation scores as the claim and transcripts as QA). Five gaps
had to be closed before it could run unattended:

1. **The Stage 2 gate was not quantitative.** "Surfaces separate the tracks
   in useful, inspectable ways" cannot drive automation. This loop defines
   the objective as the mean |paired Cohen's d| between Sol and Marrow over
   the top-k unconfounded score surfaces, pairing by `paired_group_id`, with
   explicit gates (see Metrics). The numbers are configurable defaults, not
   revealed truth — recalibrate after the first real Stage 1 run.
2. **Goodhart risk on trivial contrast.** Sol-short vs Marrow-long means a
   surface can "separate" by encoding response length. Hill climbing will
   find and exploit that. Surfaces whose per-example scores correlate with
   response length beyond a threshold are excluded from the objective and
   reported as confounded. Transcript QA stays a guardrail, never the
   objective.
3. **Fixed user turns break coherence as tracks diverge.** The user side was
   written replying to the *original* assistant; three regenerated tracks
   make some user turns non-sequiturs, more so in later turns. Mitigations:
   seeds must have user turns that press the user's own thread regardless of
   the reply (authored seeds in `factory/hillclimb/seeds.py` follow this; apply
   the same filter to ESConv), and conversations cap at 4-6 assistant turns.
   Residual incoherence is acceptable — this is a measurement demo, not a
   deployment simulation — but inspect Stage 1 transcripts for it.
4. **No reproducibility spec.** Xenon's `GenerationSpec` has no sampling
   seed, so identical reruns are not bit-reproducible and small objective
   deltas between iterations are partly noise. Treat objective changes below
   ~0.1 as noise; consider adding a `seed` field to Xenon's GenerationSpec
   (plumbs to vLLM `SamplingParams.seed`) if tighter comparisons are needed.
5. **Tier 3 does not belong in the loop.** Crisis-adjacent seeds should come
   from citable public safety benchmarks, manually curated. The seed
   validator rejects tier 3 in automated runs; add them by hand between
   Stage 2 and Stage 3.

Also amended: the plan runs scoring first at Stage 2 (25 seeds), but hill
climbing on activation separation needs scoring in the loop earlier — one
H200 capture run per iteration at 5-seed scale is the cheapest signal that
prompts move the surfaces at all. Stage gates below reflect that.

## Structure

```text
factory/hillclimb/personas.py        versioned prompts (sol_v1, marrow_v1, control_v1)
factory/hillclimb/seeds.py           staged seed sets + ESConv loader + validator
factory/hillclimb/rounds.py          per-turn round building / result ingestion
factory/hillclimb/transcript_qa.py   contrast guardrails (length, hedges, lexicon)
factory/hillclimb/normalize.py       histories -> AuditTrace rows (required metadata)
factory/hillclimb/separation.py      paired effect sizes, confound check, gates
factory/hillclimb/state.py           artifacts/demo_hillclimb/state.json
factory/workflows/demo_generation.py  one round per run, batched all seeds x tracks
factory/workflows/demo_scoring.py     tau2 scoring surfaces over demo traces
factory/scripts/demo_hillclimb.py     driver CLI
```

All working files live under `artifacts/demo_hillclimb/` (gitignored). The
final shipped dataset is curated into `data/` by hand once frozen.

## One Iteration

```bash
uv run python -m backend.scripts.demo_hillclimb run-iteration --stage 1
```

which is equivalent to:

```bash
uv run python -m backend.scripts.demo_hillclimb generate --stage 1   # N Modal generation rounds
uv run python -m backend.scripts.demo_hillclimb qa                   # transcript guardrails (local)
uv run python -m backend.scripts.demo_hillclimb normalize            # -> normalized_traces.json (local)
uv run python -m backend.scripts.demo_hillclimb score                # Modal capture + scoring
uv run python -m backend.scripts.demo_hillclimb evaluate             # separation report + gates + state
```

Generation is turn-by-turn (turn t+1 conditions on each track's own turn t),
so `generate` runs one Modal workflow per conversation turn with all
seeds x tracks batched into a single vLLM session per round. Each track sees
only its own history — never another track's.

Requirements: Modal CLI authenticated, `HF_TOKEN` set, the xenon sibling
checkout present (see `docs/xenon-modal-runbook.md`).

## Metrics And Gates

Defined in `factory/hillclimb/separation.py` (`DEFAULT_GATES`):

- **Objective:** mean |d(sol, marrow)| over the top 5 unconfounded surfaces,
  where d is Cohen's d over per-seed paired differences.
- **Pass requires:** objective ≥ 0.8; at least 3 surfaces individually at
  |d(sol, marrow)| ≥ 0.8 with control non-collapsed (|d| ≥ 0.3 against both
  personas); confounded surfaces (|corr with length| > 0.6) excluded.

Transcript QA (`factory/hillclimb/transcript_qa.py`) checks the build plan's
validation targets and names the track to sharpen. QA failing does not block
scoring — it explains a separation failure and directs the fix.

## The Hill-Climb Protocol

The driver is deterministic; the *proposal* step is judgment and belongs to
the operating agent:

1. `run-iteration --stage <n>`; read `artifacts/demo_hillclimb/separation.json`
   and `qa_report.json`.
2. If gates pass at the current stage, advance: stage 0 -> 1 -> 2 (Stage 2
   needs the 25-seed set registered in `seeds.py`, mixing in ESConv).
3. If gates fail, sharpen **one** persona: add a new version in
   `factory/hillclimb/personas.py` (never edit an existing version), update
   `prompt_ids` in `artifacts/demo_hillclimb/state.json`, and rerun. Use
   `failing_tracks` from QA and the per-surface report to decide which track
   and what to change. One variable per iteration.
4. Never chase a confounded surface: if the objective only moves on
   length-correlated surfaces, the prompts are diverging in style, not
   persona. Adjust toward content-level contrast (what the persona attends
   to), not more extreme length rules.
5. When Stage 2 passes, the driver sets `frozen: true`. After that, prompts
   do not change; Stage 3 is volume only (`generate --stage 3 --allow-frozen`
   once a Stage 3 seed set exists).

Every iteration is appended to `state.json` history with prompts, run ids,
QA and objective — the loop's memory and the eventual methodology note.

To run this long-term as an agent loop: `/loop` (or a scheduled agent) with
"run one demo hill-climb iteration, read the reports, propose and apply at
most one persona prompt version bump per the protocol in
docs/internal/demo-hillclimb.md, then stop if frozen". Budget note: one Stage 1
iteration ≈ 4 generation rounds (H100:2, minutes each warm) + 1 scoring run
(H200:2 capture + batched CPU scoring).

## First-Live-Run Checklist

Things intentionally left to verify against real artifacts (cheap to fix,
wasteful to guess):

- [ ] `rows_from_score_artifact` in `factory/hillclimb/separation.py` matches the
      actual projection/emotion/probe `result.json` layouts; tighten the
      field selection after inspecting one artifact of each kind.
- [ ] QA thresholds in `transcript_qa.THRESHOLDS` against real Llama 3.3 70B
      outputs (Stage 0), then gate thresholds after the first Stage 1 score.
- [ ] `max_model_len` 4096 still fits stage-1 final rounds (bump
      `PERSONA_AUDIT_DEMO_GENERATION_MAX_MODEL_LEN` if prompts grow).
- [ ] ESConv download + `load_esconv_seeds` filtering quality before Stage 2
      (needs 25 seeds; tag tiers by hand; document cc-by-nc-4.0 provenance).
