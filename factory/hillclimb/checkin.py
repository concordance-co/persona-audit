"""Check-in digest for credit-cheap agent monitoring of the hill climb.

Produces a compact report plus a single recommended action from a fixed
decision table, so a monitoring agent can operate by reading ~40 lines and
running at most one command (docs/demo-monitoring-plan.md). Everything here
is deterministic; anything requiring judgment is routed to ESCALATE/HOLD.

Actions:
- RUN_ITERATION     mechanical; the monitor may execute the given command
- FINISH_ITERATION  mechanical; generation done but the pipeline tail is not
- WAIT_RUNNING      mechanical; a prior iteration is still running
- ESCALATE_PROMPT   needs a strong model or human to author a prompt version
- HOLD_HUMAN        blocked on human-only work (seed curation, stage 3 scale)
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from factory.hillclimb.state import HillClimbState

STALL_WINDOW = 2

_DRIVER = "uv run python -m factory.scripts.demo_hillclimb"


def decide(
    state: HillClimbState,
    *,
    has_transcripts: bool,
    has_separation: bool,
    qa_failing_tracks: list[str] | None = None,
    active_run: Mapping[str, Any] | None = None,
    stage2_seeds_ready: bool = False,
) -> dict[str, Any]:
    last = state.history[-1] if state.history else None

    if active_run:
        if active_run.get("stale"):
            return _hold(
                "A stale active-run lock is present: "
                f"{active_run.get('reason', 'unknown reason')}. Inspect "
                f"{active_run.get('path', 'active_run.json')} before launching more Modal work."
            )
        return {
            "action": "WAIT_RUNNING",
            "command": None,
            "reason": (
                "A demo hill-climb command is already running "
                f"(pid={active_run.get('pid')}, command={active_run.get('command')!r}, "
                f"started_at={active_run.get('started_at')}). Do not launch another Modal run."
            ),
        }
    if state.frozen:
        return _hold(
            "Done: Stage 2 passed, prompts are frozen, and the demo dataset is saved "
            "under data/demo/stage2/ (25 conversations x 3 tracks). The loop stops here. "
            "Stage 3 is optional volume only (more seeds, same frozen prompts): "
            f"`{_DRIVER} generate --stage 3 --allow-frozen`."
        )
    if last is None and not has_transcripts:
        return _run(0, "No iterations yet; bootstrap Stage 0.")
    if last is None or (has_transcripts and not has_separation and _mid_iteration(state, last)):
        return {
            "action": "FINISH_ITERATION",
            "command": f"{_DRIVER} qa && {_DRIVER} normalize && {_DRIVER} score && {_DRIVER} evaluate",
            "reason": "Generation output exists but the iteration was not evaluated.",
        }
    if dict(state.prompt_ids) != dict(last.get("prompt_ids") or {}):
        return _run(
            state.stage,
            f"Prompt ids changed to {state.prompt_ids} but have not been tested.",
        )
    if last.get("separation_passed"):
        # Advancing requires the transcripts to read as intended too, not just
        # the activation gates: a persona that separates on surfaces but reads
        # mushy (or vice versa) is not demo-quality data.
        if last.get("qa_passed") is False:
            tracks = f" (tracks: {qa_failing_tracks})" if qa_failing_tracks else ""
            return _escalate(
                "Separation gates pass but transcript QA fails"
                f"{tracks}. Author a sharper prompt version for the failing "
                "track before advancing a stage; see qa_report.json checks."
            )
        if state.stage <= 0:
            return _run(1, "Stage 0 separation gates pass; advance to Stage 1 (5 seeds).")
        if state.stage == 1:
            if stage2_seeds_ready:
                return _run(
                    2,
                    "Stage 1 gates pass and the 25-seed Stage 2 set is registered; advance to Stage 2.",
                )
            return _hold(
                "Stage 1 gates pass. Stage 2 needs the 25-seed set registered in "
                "factory/hillclimb/seeds.py (mix in ESConv, tag tiers by hand) before proceeding."
            )
        return _hold("Stage >= 2 passed; expected frozen state. Inspect state.json.")

    # Separation failed.
    if len(state.history) > STALL_WINDOW and (
        state.best_iteration is None or state.best_iteration <= state.iteration - STALL_WINDOW
    ):
        return _escalate(
            f"Objective has not improved in {STALL_WINDOW}+ iterations "
            f"(best {state.best_objective} at iteration {state.best_iteration}). "
            "Prompt-space redesign needed; review separation.json per-surface report."
        )
    if qa_failing_tracks:
        return _escalate(
            f"Separation below gates and transcript QA names the mushy track(s): "
            f"{qa_failing_tracks}. Author a sharper prompt version for that track only."
        )
    return _escalate(
        "Separation below gates with QA clean: the contrast is stylistic but not moving "
        "activation surfaces. Review separation.json (confounded/top surfaces) and revise "
        "one persona toward content-level contrast."
    )


def _mid_iteration(state: HillClimbState, last: Mapping[str, Any]) -> bool:
    return int(last.get("iteration", -1)) != state.iteration


def _run(stage: int, reason: str) -> dict[str, Any]:
    return {
        "action": "RUN_ITERATION",
        "stage": stage,
        "command": f"{_DRIVER} run-iteration --stage {stage}",
        "reason": reason,
    }


def _escalate(reason: str) -> dict[str, Any]:
    return {"action": "ESCALATE_PROMPT", "command": None, "reason": reason}


def _hold(reason: str) -> dict[str, Any]:
    return {"action": "HOLD_HUMAN", "command": None, "reason": reason}


def render_markdown(
    state: HillClimbState,
    decision: Mapping[str, Any],
    *,
    separation: Mapping[str, Any] | None = None,
    qa: Mapping[str, Any] | None = None,
) -> str:
    recent = state.history[-3:]
    lines = [
        "# Demo Hill-Climb Check-In",
        "",
        f"- stage: {state.stage}  iteration: {state.iteration}  frozen: {state.frozen}",
        f"- prompts: {state.prompt_ids}",
        f"- best objective: {state.best_objective} (iteration {state.best_iteration})",
    ]
    if recent:
        trend = ", ".join(f"#{entry.get('iteration')}: {entry.get('objective')}" for entry in recent)
        lines.append(f"- recent objectives: {trend}")
    if qa is not None:
        lines.append(
            f"- last QA: {'pass' if qa.get('passed') else 'FAIL'}"
            + (f" (sharpen: {qa.get('failing_tracks')})" if qa.get("failing_tracks") else "")
        )
    if separation is not None:
        lines.extend(
            [
                f"- last separation: {'pass' if separation.get('passed') else 'FAIL'} "
                f"objective={separation.get('objective'):.3f}",
                f"- separated surfaces: {_format_names(separation.get('separated_surfaces'))}",
                f"- top surfaces: {_format_names(separation.get('top_surfaces'))}",
                f"- confounded (excluded): {_format_names(separation.get('confounded_surfaces'))}",
            ]
        )
        for reason in separation.get("reasons", []):
            lines.append(f"  - gate: {reason}")
    lines.extend(
        [
            "",
            f"## Recommended action: {decision['action']}",
            "",
            decision["reason"],
        ]
    )
    if decision.get("command"):
        lines.extend(["", "```bash", str(decision["command"]), "```"])
    return "\n".join(lines)


def escalator_brief(reason: str) -> str:
    """The bounded task handed to the escalator agent by `tick`.

    This is the only place a model touches the loop: author one prompt
    version for one track. Everything else is deterministic.
    """

    return f"""You are the prompt escalator for the persona-audit demo hill-climb (protocol: docs/demo-hillclimb.md).

Escalation reason: {reason}

Do exactly this, nothing more:
1. Read artifacts/demo_hillclimb/separation.json, artifacts/demo_hillclimb/qa_report.json, and factory/hillclimb/personas.py.
2. Pick the single track (sol or marrow) most responsible for the failure and author ONE new PersonaPrompt version for it in factory/hillclimb/personas.py: copy the latest version for that track, bump version and prompt_id (sol_v1 -> sol_v2), register it in PROMPTS. Never edit or delete an existing version. Aim the revision directly at the failing checks and surfaces named in the reports.
3. Update that one track's entry under "prompt_ids" in artifacts/demo_hillclimb/state.json to the new prompt_id. Change nothing else in that file.
4. Run `uv run pytest tests/test_demo_structure.py -q` to confirm nothing broke, then stop.

Hard limits: never run generate, score, run-iteration, tick, or any Modal/xenon command; never edit seeds, gates, QA thresholds, tests, or any file other than factory/hillclimb/personas.py and artifacts/demo_hillclimb/state.json; never change more than one track's prompt. The next tick tests your prompt automatically."""


def _format_names(value: Any, *, limit: int = 8) -> str:
    names = list(value or [])
    if not names:
        return "[]"
    shown = ", ".join(str(name) for name in names[:limit])
    if len(names) > limit:
        shown = f"{shown}, ... (+{len(names) - limit} more)"
    return f"[{shown}]"
