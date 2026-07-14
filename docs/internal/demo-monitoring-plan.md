# Demo Hill-Climb Autonomy Plan

How the climb to good demo data runs unattended without burning credits.
Design principle: **no agent is ever in the mechanical loop.** A deterministic
heartbeat does everything scriptable; a model is invoked only at the single
judgment point (authoring a prompt revision), and the loop itself rate-limits
that to at most once per iteration.

## The One Command

```bash
uv run python -m backend.scripts.demo_hillclimb tick
```

Each tick: run the check-in (digest appended to
`artifacts/demo_hillclimb/checkins.log`), then execute its decision inline —
no agent reads the digest, no agent waits on Modal:

| Decision | What tick does | Tokens |
| --- | --- | --- |
| `RUN_ITERATION` | runs the full iteration in-process (generate → qa → normalize → score → evaluate) | 0 |
| `FINISH_ITERATION` | runs the pipeline tail in-process | 0 |
| `WAIT_RUNNING` | exits 0 — a previous tick's iteration still holds the run lock | 0 |
| `HOLD_HUMAN` | exits 3 — blocked on human-only work (Stage 2 seed curation, Stage 3 scale) | 0 |
| `ESCALATE_PROMPT` | launches the escalator agent once (see below), exits 0 if it bumped a prompt, 3 otherwise | one bounded agent run |

Cron is the whole scheduler (requires `HF_TOKEN` and Modal auth in the
environment; the run lock makes overlapping ticks harmless):

```cron
*/15 * * * * cd $HOME/repos/concordance/persona-audit && uv run python -m backend.scripts.demo_hillclimb tick >> artifacts/demo_hillclimb/tick.log 2>&1
```

Modal spend is bounded by the decision table, not the cadence: a tick only
starts an iteration when the previous one is evaluated and the table says
run, stage advances are gated on separation + QA both passing, and Stage ≥ 2
freezes prompts. Ticking every 15 minutes does not multiply GPU cost.

## The Escalator (the only agent)

When the gates fail and mechanics can't help — objective stalled, or a track
reads mushy — tick launches the command in `DEMO_HILLCLIMB_ESCALATOR_CMD`
(e.g. `claude -p --model sonnet` or `codex exec`) with a fixed brief appended
(`factory/hillclimb/checkin.py:escalator_brief`). The brief allows exactly one
move: read `separation.json` + `qa_report.json`, author ONE new prompt
version for ONE track in `factory/hillclimb/personas.py`, point `prompt_ids` at it
in `state.json`, stop. No Modal commands, no other files, no second track.
The next tick sees the untested prompt set and runs the iteration
mechanically — the agent never launches GPU work.

**Auth under cron (macOS):** a cron job cannot reach the login keychain where
Claude Code stores its OAuth token, so a subscription-logged-in `claude` prints
"Not logged in" and the escalator no-ops. For hands-off autonomy, give the
escalator an API key via a locked-down env file the cron line sources
(`. $HOME/.demo_hillclimb.env`, `chmod 600`, containing
`export ANTHROPIC_API_KEY=...`) — never inline in the crontab, where it would
show in `crontab -l` and `ps`. The key reaches the `claude` subprocess by
normal environment inheritance; mechanical ticks never touch it.

Guards that keep this cheap and safe:

- **Once per attempt:** `artifacts/demo_hillclimb/last_escalation.json`
  records (iteration, prompt_ids) before launching; the same pair never
  re-fires the escalator. A crashed or do-nothing escalator degrades to
  "needs human" (exit 3), not a retry loop.
- **Unset by default:** without `DEMO_HILLCLIMB_ESCALATOR_CMD`, tick prints
  the escalation reason and exits 3 — you do the revision yourself per
  docs/internal/demo-hillclimb.md. Set the variable only when you want true autonomy.
- **Verifiable:** every escalation is one commit-sized diff (a new
  PersonaPrompt version) — easy to review in `git diff factory/hillclimb/personas.py`.

## Watching It

Read files, not agents:

- **`artifacts/demo_hillclimb/report.html` — the dashboard.** Open it in a
  browser (`open artifacts/demo_hillclimb/report.html`); it auto-refreshes
  every 60s and is regenerated at the start and end of every tick. Stat tiles,
  objective trend, top-surface effect sizes, QA checks, iteration history,
  and the tick log tail. Regenerate manually anytime with
  `uv run python -m backend.scripts.demo_hillclimb report`.
- `artifacts/demo_hillclimb/tick.log` — every tick's digest + what it did
- `artifacts/demo_hillclimb/checkins.log` — digest history (same content, structured)
- `git diff factory/hillclimb/personas.py` — every prompt revision the escalator made
- `uv run python -m backend.scripts.demo_hillclimb status` — instant state

Exit code 3 in the tick log (grep `Recommended action: HOLD_HUMAN` or
`needs-human`) means the loop is parked waiting for you: Stage 2 seed
curation, or an escalation the agent couldn't resolve.

`checkin --log` still exists as the read-only digest for humans or ad hoc
agent sessions; it never executes anything.

## Tuning

- **Pause the loop:** comment out the cron line, or leave `HOLD_HUMAN` states
  parked (ticks are then near-instant no-ops).
- **Manual judgment:** unset `DEMO_HILLCLIMB_ESCALATOR_CMD` and handle
  escalations yourself in an interactive session.
- **Stage 3 scale runs:** disable the cron; run
  `generate --stage 3 --allow-frozen` manually and watch it directly.
