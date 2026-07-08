"""Driver for the demo-dataset hill-climb loop (docs/demo-hillclimb.md).

Deterministic mechanics: generate rounds through the Xenon/Modal workflow,
run transcript QA, normalize traces, run scoring, and evaluate
activation-score separation against the stage gates. The judgment step —
reading a failing report and sharpening one persona prompt (a new version in
backend/demo/personas.py) — is delegated to a bounded escalator agent by
`tick`, the autonomous heartbeat (docs/demo-monitoring-plan.md).

Usage (from the repo root):

    uv run python -m backend.scripts.demo_hillclimb status
    uv run python -m backend.scripts.demo_hillclimb tick          # cron this
    uv run python -m backend.scripts.demo_hillclimb checkin --log # digest only
    uv run python -m backend.scripts.demo_hillclimb run-iteration --stage 1
    uv run python -m backend.scripts.demo_hillclimb generate --stage 0
    uv run python -m backend.scripts.demo_hillclimb qa
    uv run python -m backend.scripts.demo_hillclimb normalize
    uv run python -m backend.scripts.demo_hillclimb score
    uv run python -m backend.scripts.demo_hillclimb evaluate
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable

from pipelines_v2.api import ModalVolumeStore, TransferPolicy

from backend.demo import checkin as demo_checkin
from backend.demo import normalize as demo_normalize
from backend.demo import report_html as demo_report
from backend.demo import rounds as demo_rounds
from backend.demo import run_lock as demo_run_lock
from backend.demo import separation as demo_separation
from backend.demo import transcript_qa
from backend.demo.personas import prompt as persona_prompt
from backend.demo.seeds import seeds_for_stage, validate_seeds
from backend.demo.state import HILLCLIMB_ROOT, STATE_PATH, HillClimbState, load_state, save_state
from backend.paths import REPO_ROOT
from backend.workflows.common import ARTIFACT_VOLUME_NAME
from backend.workflows.demo_generation import (
    GENERATION_PARAMS,
    ROUND_FILE_ENV,
)
from backend.workflows.demo_generation import (
    MODAL_ARTIFACT_ROOT as GENERATION_ARTIFACT_ROOT,
)
from backend.workflows.demo_scoring import (
    MODAL_ARTIFACT_ROOT as SCORING_ARTIFACT_ROOT,
)
from backend.workflows.demo_scoring import (
    TRACES_FILE_ENV,
)

WRAPPER = REPO_ROOT / "backend" / "scripts" / "run_xenon_workflow.sh"
GENERATION_WORKFLOW = REPO_ROOT / "backend" / "workflows" / "demo_generation.py"
SCORING_WORKFLOW = REPO_ROOT / "backend" / "workflows" / "demo_scoring.py"

TRANSCRIPTS_PATH = HILLCLIMB_ROOT / "transcripts.json"
QA_REPORT_PATH = HILLCLIMB_ROOT / "qa_report.json"
TRACES_PATH = HILLCLIMB_ROOT / "normalized_traces.json"
SCORE_RUN_PATH = HILLCLIMB_ROOT / "score_run.json"
SEPARATION_PATH = HILLCLIMB_ROOT / "separation.json"
CHECKIN_LOG_PATH = HILLCLIMB_ROOT / "checkins.log"
TICK_LOG_PATH = HILLCLIMB_ROOT / "tick.log"
REPORT_PATH = HILLCLIMB_ROOT / "report.html"
ESCALATION_MARKER_PATH = HILLCLIMB_ROOT / "last_escalation.json"

# Shell command tick uses to launch the escalator agent on ESCALATE_PROMPT,
# e.g. "claude -p --model sonnet" or "codex exec". The escalator brief is
# appended as the final argument. Unset = tick reports and exits 3 instead.
ESCALATOR_CMD_ENV = "DEMO_HILLCLIMB_ESCALATOR_CMD"


def _stage2_seeds_ready() -> bool:
    """True once the Stage 2 seed set is registered (lets the loop auto-advance)."""

    try:
        seeds_for_stage(2)
        return True
    except NotImplementedError:
        return False


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _run_workflow(workflow_file: Path, extra_env: dict[str, str] | None = None) -> dict[str, Any]:
    """Run a workflow via the wrapper; stdout is the JSON result, stderr streams live."""

    env = {**os.environ, **(extra_env or {})}
    result = subprocess.run(
        [str(WRAPPER), "run", "--file", str(workflow_file), "--logging", "INFO"],
        env=env,
        stdout=subprocess.PIPE,
        text=True,
        check=True,
    )
    return json.loads(result.stdout)


def _localize_artifact(artifact_root: str, artifact_id: str) -> Path:
    store = ModalVolumeStore(
        name=ARTIFACT_VOLUME_NAME,
        root=artifact_root,
        local_cache_root=HILLCLIMB_ROOT / "modal_cache" / Path(artifact_root).name,
        transfer_policy=TransferPolicy(allow_large_transfer=True),
    )
    return store.localize(artifact_id)


def cmd_status(_: argparse.Namespace) -> int:
    state = load_state()
    active = demo_run_lock.active_run()
    print(json.dumps(
        {
            "stage": state.stage,
            "iteration": state.iteration,
            "prompt_ids": state.prompt_ids,
            "frozen": state.frozen,
            "best_objective": state.best_objective,
            "best_iteration": state.best_iteration,
            "iterations_recorded": len(state.history),
            "artifacts": {
                "transcripts": TRANSCRIPTS_PATH.exists(),
                "qa_report": QA_REPORT_PATH.exists(),
                "normalized_traces": TRACES_PATH.exists(),
                "score_run": SCORE_RUN_PATH.exists(),
                "separation": SEPARATION_PATH.exists(),
            },
            "active_run": active,
        },
        indent=2,
    ))
    return 0


def cmd_generate(ns: argparse.Namespace) -> int:
    state = load_state()
    if state.frozen and not ns.allow_frozen:
        print(
            "Prompts are frozen (Stage 2 passed). Rerun with --allow-frozen for scale runs; "
            "do not tune prompts.",
            file=sys.stderr,
        )
        return 2
    seeds = seeds_for_stage(ns.stage)
    problems = validate_seeds(seeds)
    if problems:
        for problem in problems:
            print(f"seed problem: {problem}", file=sys.stderr)
        return 2

    prompts = {track: persona_prompt(pid) for track, pid in state.prompt_ids.items()}
    state.stage = ns.stage
    state.iteration += 1
    histories: demo_rounds.Histories = {}
    run_ids: list[str] = []
    total_rounds = ns.turns or demo_rounds.max_rounds(seeds)

    for turn_index in range(total_rounds):
        examples = demo_rounds.build_round_examples(
            seeds, prompts, histories, turn_index, stage=ns.stage
        )
        if not examples:
            break
        round_file = HILLCLIMB_ROOT / "rounds" / f"iter{state.iteration:03d}_t{turn_index:02d}.json"
        _write_json(round_file, {"stage": ns.stage, "turn_index": turn_index, "examples": examples})
        print(f"round {turn_index}: {len(examples)} examples -> workflow run", file=sys.stderr)
        payload = _run_workflow(GENERATION_WORKFLOW, {ROUND_FILE_ENV: str(round_file)})
        run_ids.append(str(payload.get("run_id")))
        step = payload["steps"]["generate_round"]
        artifact_dir = _localize_artifact(GENERATION_ARTIFACT_ROOT, str(step["artifact_id"]))
        result = _read_json(artifact_dir / "result.json")
        rows = result.get("rows") or result.get("records") or []
        demo_rounds.apply_round_results(histories, seeds, prompts, turn_index, rows)

    _write_json(
        TRANSCRIPTS_PATH,
        {
            "stage": ns.stage,
            "iteration": state.iteration,
            "prompt_ids": state.prompt_ids,
            "generation_params": GENERATION_PARAMS,
            "run_ids": run_ids,
            "histories": demo_rounds.histories_to_json(histories),
        },
    )
    save_state(state)
    print(f"generated {total_rounds} rounds over {len(seeds)} seeds -> {TRANSCRIPTS_PATH}")
    return 0


def _load_histories() -> tuple[dict[str, Any], demo_rounds.Histories]:
    transcripts = _read_json(TRANSCRIPTS_PATH)
    return transcripts, demo_rounds.histories_from_json(transcripts["histories"])


def cmd_qa(_: argparse.Namespace) -> int:
    transcripts, histories = _load_histories()
    track_turns: dict[str, list[str]] = {}
    for (_, track), turns in histories.items():
        track_turns.setdefault(track, []).extend(turns)
    report = transcript_qa.qa_report(track_turns)
    _write_json(QA_REPORT_PATH, report)
    for check in report["checks"]:
        marker = "PASS" if check["passed"] else "FAIL"
        print(f"[{marker}] {check['name']}: {check['value']}")
    if report["failing_tracks"]:
        print(f"failing tracks to sharpen: {report['failing_tracks']}")
    print(f"qa {'passed' if report['passed'] else 'failed'} -> {QA_REPORT_PATH}")
    return 0 if report["passed"] else 1


def cmd_normalize(_: argparse.Namespace) -> int:
    transcripts, histories = _load_histories()
    seeds = seeds_for_stage(int(transcripts["stage"]))
    prompts = {track: persona_prompt(pid) for track, pid in transcripts["prompt_ids"].items()}
    traces = demo_normalize.traces_from_histories(
        seeds, prompts, histories, generation_params=transcripts["generation_params"]
    )
    demo_normalize.save_traces(traces, TRACES_PATH)
    print(f"normalized {len(traces)} traces -> {TRACES_PATH}")
    return 0


def cmd_score(_: argparse.Namespace) -> int:
    payload = _run_workflow(SCORING_WORKFLOW, {TRACES_FILE_ENV: str(TRACES_PATH)})
    _write_json(SCORE_RUN_PATH, payload)
    print(f"scoring run {payload.get('run_id')} -> {SCORE_RUN_PATH}")
    return 0


def _assistant_turn_lengths() -> dict[tuple[str, int], float]:
    """(trace_id, assistant_turn_index) -> word count, for the confound guard."""

    if not TRACES_PATH.exists():
        return {}
    lengths: dict[tuple[str, int], float] = {}
    for trace in demo_normalize.load_traces(TRACES_PATH):
        assistant_index = 0
        for turn in trace.turns:
            if turn.role == "assistant":
                lengths[(trace.trace_id, assistant_index)] = float(len(turn.content.split()))
                assistant_index += 1
    return lengths


def cmd_evaluate(_: argparse.Namespace) -> int:
    score_run = _read_json(SCORE_RUN_PATH)
    lengths = _assistant_turn_lengths()
    row_groups: list[list[dict[str, Any]]] = []
    for step_name, step in score_run.get("steps", {}).items():
        if not step_name.startswith("score_"):
            continue
        artifact_id = step.get("artifact_id")
        if not artifact_id:
            continue
        artifact_dir = _localize_artifact(SCORING_ARTIFACT_ROOT, str(artifact_id))
        result_path = artifact_dir / "result.json"
        if not result_path.exists():
            print(f"skipping {step_name}: no result.json in artifact", file=sys.stderr)
            continue
        rows = demo_separation.rows_from_score_artifact(
            _read_json(result_path), surface_prefix=f"{step_name}.", lengths=lengths
        )
        print(f"{step_name}: {len(rows)} score rows", file=sys.stderr)
        row_groups.append(rows)

    merged = demo_separation.merge_rows(*row_groups)
    if not merged:
        print(
            "No separation rows extracted. Inspect a score artifact result.json and adjust "
            "backend/demo/separation.py:rows_from_score_artifact to its layout.",
            file=sys.stderr,
        )
        return 2
    report = demo_separation.separation_report(merged)
    _write_json(SEPARATION_PATH, report)

    state = load_state()
    qa_passed = _read_json(QA_REPORT_PATH)["passed"] if QA_REPORT_PATH.exists() else None
    state.record_iteration(
        {
            "stage": state.stage,
            "prompt_ids": dict(state.prompt_ids),
            "qa_passed": qa_passed,
            "objective": report["objective"],
            "separation_passed": report["passed"],
            "top_surfaces": report["top_surfaces"],
            "confounded_surfaces": report["confounded_surfaces"],
            "score_run_id": score_run.get("run_id"),
        }
    )
    froze = report["passed"] and state.stage >= 2 and not state.frozen
    if froze:
        state.frozen = True
        print("Stage 2 gate passed: prompts are now FROZEN. Dataset is demo-ready.")
    save_state(state)

    if froze:
        _write_snapshot(
            f"stage{state.stage}",
            note=(
                f"Auto-saved on Stage {state.stage} freeze: separation and QA gates passed, "
                "prompts frozen. Shippable demo dataset."
            ),
        )

    print(f"objective (mean |d| top surfaces): {report['objective']:.3f}")
    print(f"separated surfaces: {report['separated_surfaces']}")
    if report["confounded_surfaces"]:
        print(f"length-confounded (excluded): {report['confounded_surfaces']}")
    for reason in report["reasons"]:
        print(f"gate: {reason}")
    print(f"separation {'passed' if report['passed'] else 'failed'} -> {SEPARATION_PATH}")
    return 0 if report["passed"] else 1


def _checkin(*, log: bool) -> tuple[HillClimbState, dict[str, Any]]:
    """Load state, decide, print (and optionally log) the digest."""

    state = load_state()
    qa = _read_json(QA_REPORT_PATH) if QA_REPORT_PATH.exists() else None
    separation = _read_json(SEPARATION_PATH) if SEPARATION_PATH.exists() else None
    decision = demo_checkin.decide(
        state,
        has_transcripts=TRANSCRIPTS_PATH.exists(),
        has_separation=SEPARATION_PATH.exists(),
        qa_failing_tracks=(qa or {}).get("failing_tracks") or None,
        active_run=demo_run_lock.active_run(),
        stage2_seeds_ready=_stage2_seeds_ready(),
    )
    digest = demo_checkin.render_markdown(state, decision, separation=separation, qa=qa)
    print(digest)
    if log:
        from datetime import datetime, timezone

        CHECKIN_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with CHECKIN_LOG_PATH.open("a", encoding="utf-8") as handle:
            handle.write(f"\n---\n<!-- checkin {stamp} -->\n{digest}\n")
    return state, decision


def cmd_checkin(ns: argparse.Namespace) -> int:
    """Compact digest + one recommended action. Exit 0 = mechanical, 3 = needs judgment."""

    _, decision = _checkin(log=ns.log)
    return 0 if decision["action"] in {"RUN_ITERATION", "FINISH_ITERATION", "WAIT_RUNNING"} else 3


def _run_pipeline(
    ns: argparse.Namespace,
    steps: tuple[Callable[[argparse.Namespace], int], ...],
    lock_metadata: dict[str, Any],
) -> int:
    try:
        with demo_run_lock.run_lock(lock_metadata):
            for step in steps:
                code = step(ns)
                # QA failure still proceeds to scoring: separation and QA are
                # evaluated together at the decision table, and QA names the
                # track to sharpen when the gates fail.
                if code != 0 and step is not cmd_qa:
                    return code
            return 0
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 2


def cmd_run_iteration(ns: argparse.Namespace) -> int:
    command = f"run-iteration --stage {ns.stage}"
    if ns.turns is not None:
        command = f"{command} --turns {ns.turns}"
    if ns.allow_frozen:
        command = f"{command} --allow-frozen"
    steps = (cmd_generate, cmd_qa, cmd_normalize, cmd_score, cmd_evaluate)
    return _run_pipeline(ns, steps, {"command": command, "stage": ns.stage})


def _finish_iteration(state: HillClimbState) -> int:
    ns = argparse.Namespace(stage=state.stage, turns=None, allow_frozen=False)
    steps = (cmd_qa, cmd_normalize, cmd_score, cmd_evaluate)
    return _run_pipeline(ns, steps, {"command": "finish-iteration", "stage": state.stage})


def _escalate_prompt(state: HillClimbState, reason: str) -> int:
    """Launch the bounded escalator agent once per (iteration, prompt set)."""

    marker = _read_json(ESCALATION_MARKER_PATH) if ESCALATION_MARKER_PATH.exists() else None
    if (
        marker
        and marker.get("iteration") == state.iteration
        and marker.get("prompt_ids") == dict(state.prompt_ids)
    ):
        print(
            f"Already escalated iteration {state.iteration} without a prompt change; "
            "a human should review (see docs/demo-hillclimb.md).",
            file=sys.stderr,
        )
        return 3
    escalator_cmd = os.environ.get(ESCALATOR_CMD_ENV)
    if not escalator_cmd:
        print(
            f"ESCALATE_PROMPT: set {ESCALATOR_CMD_ENV} (e.g. 'claude -p --model sonnet' or "
            "'codex exec') to let tick launch the escalator agent, or revise the prompt "
            "yourself per docs/demo-hillclimb.md.",
            file=sys.stderr,
        )
        return 3

    from datetime import datetime, timezone

    # Written before launching so a crashing escalator cannot re-fire every tick.
    _write_json(
        ESCALATION_MARKER_PATH,
        {
            "iteration": state.iteration,
            "prompt_ids": dict(state.prompt_ids),
            "reason": reason,
            "started_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        },
    )
    brief = demo_checkin.escalator_brief(reason)
    print(f"launching escalator: {escalator_cmd}", file=sys.stderr)
    # The brief goes over stdin, not argv: variadic CLI flags (e.g. claude's
    # --allowedTools) would otherwise swallow a trailing positional prompt.
    subprocess.run(shlex.split(escalator_cmd), input=brief, text=True, check=False)

    new_state = load_state()
    if dict(new_state.prompt_ids) != dict(state.prompt_ids):
        print(
            f"escalator bumped prompts to {new_state.prompt_ids}; "
            "the next tick will run the iteration."
        )
        return 0
    print("escalator ran but did not change prompt_ids; a human should review.", file=sys.stderr)
    return 3


def _write_report() -> None:
    """Regenerate the static monitoring dashboard from current artifacts."""

    from datetime import datetime, timezone

    state = load_state()
    qa = _read_json(QA_REPORT_PATH) if QA_REPORT_PATH.exists() else None
    separation = _read_json(SEPARATION_PATH) if SEPARATION_PATH.exists() else None
    decision = demo_checkin.decide(
        state,
        has_transcripts=TRANSCRIPTS_PATH.exists(),
        has_separation=SEPARATION_PATH.exists(),
        qa_failing_tracks=(qa or {}).get("failing_tracks") or None,
        active_run=demo_run_lock.active_run(),
        stage2_seeds_ready=_stage2_seeds_ready(),
    )
    log_tail = ""
    if TICK_LOG_PATH.exists():
        log_tail = "\n".join(
            TICK_LOG_PATH.read_text(encoding="utf-8").splitlines()[-40:]
        )
    escalation = (
        _read_json(ESCALATION_MARKER_PATH) if ESCALATION_MARKER_PATH.exists() else None
    )
    page = demo_report.render(
        state=demo_report.state_to_dict(state),
        decision=decision,
        qa=qa,
        separation=separation,
        active_run=demo_run_lock.active_run(),
        escalation=escalation,
        log_tail=log_tail,
        generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
    )
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(page, encoding="utf-8")


def cmd_report(_: argparse.Namespace) -> int:
    _write_report()
    print(f"dashboard -> {REPORT_PATH}")
    return 0


SNAPSHOT_ROOT = REPO_ROOT / "data" / "demo"
_SNAPSHOT_FILES = (
    ("transcripts.json", TRANSCRIPTS_PATH),
    ("normalized_traces.json", TRACES_PATH),
    ("separation.json", SEPARATION_PATH),
    ("qa_report.json", QA_REPORT_PATH),
    ("score_run.json", SCORE_RUN_PATH),
    ("state.json", STATE_PATH),
)


def _write_snapshot(label: str, note: str = "") -> Path:
    """Freeze the current validated artifacts into a committed fallback under data/demo/.

    The live artifacts under artifacts/demo_hillclimb/ are gitignored and get
    overwritten by the next iteration; this copies them (plus the exact prompt
    texts and a manifest) into a tracked, self-describing directory so a stage
    can be restored or shipped without re-running Modal. Called by `snapshot`
    and automatically on the Stage 2 freeze.
    """

    from datetime import datetime, timezone

    state = load_state()
    dest = SNAPSHOT_ROOT / label
    dest.mkdir(parents=True, exist_ok=True)

    copied: list[str] = []
    for name, path in _SNAPSHOT_FILES:
        if path.exists():
            (dest / name).write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
            copied.append(name)

    prompts = {}
    for track, pid in state.prompt_ids.items():
        persona = persona_prompt(pid)
        prompts[track] = {
            "prompt_id": persona.prompt_id,
            "version": persona.version,
            "system_prompt": persona.system_prompt,
        }

    separation = _read_json(SEPARATION_PATH) if SEPARATION_PATH.exists() else {}
    qa = _read_json(QA_REPORT_PATH) if QA_REPORT_PATH.exists() else {}
    last = state.history[-1] if state.history else {}
    manifest = {
        "label": label,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "stage": state.stage,
        "iteration": state.iteration,
        "frozen": state.frozen,
        "prompt_ids": dict(state.prompt_ids),
        "prompts": prompts,
        "objective": last.get("objective"),
        "separation_passed": separation.get("passed"),
        "qa_passed": qa.get("passed"),
        "gates": separation.get("gates"),
        "top_surfaces": separation.get("top_surfaces"),
        "files": copied,
        "note": note,
        "provenance": "Generated via backend/scripts/demo_hillclimb.py on Modal; see docs/demo-hillclimb.md.",
    }
    _write_json(dest / "manifest.json", manifest)

    obj = manifest["objective"]
    obj_text = f"{obj:.3f}" if isinstance(obj, (int, float)) else "n/a"
    readme = (
        f"# Demo dataset snapshot: {label}\n\n"
        f"Frozen {manifest['created_at']} from stage {state.stage}, iteration {state.iteration}.\n\n"
        f"- Separation gate: {'PASS' if separation.get('passed') else 'FAIL'} (objective {obj_text})\n"
        f"- Transcript QA: {'PASS' if qa.get('passed') else 'FAIL'}\n"
        f"- Prompts: {', '.join(f'{t}={p}' for t, p in sorted(state.prompt_ids.items()))}\n\n"
        f"{note + chr(10) + chr(10) if note else ''}"
        "`normalized_traces.json` is the shippable dataset (AuditTrace rows). "
        "`manifest.json` carries the exact prompt texts and gate results. "
        "Regenerate with `demo_hillclimb run-iteration`; see docs/demo-hillclimb.md.\n"
    )
    (dest / "README.md").write_text(readme, encoding="utf-8")

    print(f"snapshot '{label}' -> {dest} ({len(copied)} artifacts + manifest + README)")
    return dest


def cmd_snapshot(ns: argparse.Namespace) -> int:
    _write_snapshot(ns.label, ns.note)
    return 0


def cmd_tick(_: argparse.Namespace) -> int:
    """One autonomous heartbeat: check in, then do whatever the decision says.

    Mechanical actions run inline in this process (the run lock prevents
    overlapping ticks). ESCALATE_PROMPT launches the bounded escalator agent.
    Designed to run from cron; no agent supervises it.
    """

    state, decision = _checkin(log=True)
    _write_report()

    # Safety net: a frozen stage must always have its committed snapshot, even
    # if the run that froze it missed the auto-save (e.g. older code in-flight).
    if state.frozen and not (SNAPSHOT_ROOT / f"stage{state.stage}").exists():
        _write_snapshot(
            f"stage{state.stage}",
            note=f"Backfilled snapshot for frozen Stage {state.stage} (auto-save safety net).",
        )

    action = decision["action"]
    try:
        if action == "WAIT_RUNNING":
            return 0
        if action == "HOLD_HUMAN":
            return 3
        if action == "RUN_ITERATION":
            ns = argparse.Namespace(stage=int(decision["stage"]), turns=None, allow_frozen=False)
            return cmd_run_iteration(ns)
        if action == "FINISH_ITERATION":
            return _finish_iteration(state)
        if action == "ESCALATE_PROMPT":
            return _escalate_prompt(state, str(decision["reason"]))
        print(f"unknown action {action!r}", file=sys.stderr)
        return 3
    finally:
        _write_report()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status").set_defaults(fn=cmd_status)

    generate = sub.add_parser("generate")
    generate.add_argument("--stage", type=int, required=True)
    generate.add_argument("--turns", type=int, default=None, help="limit rounds (default: all user turns)")
    generate.add_argument("--allow-frozen", action="store_true")
    generate.set_defaults(fn=cmd_generate)

    sub.add_parser("qa").set_defaults(fn=cmd_qa)
    sub.add_parser("normalize").set_defaults(fn=cmd_normalize)
    sub.add_parser("score").set_defaults(fn=cmd_score)
    sub.add_parser("evaluate").set_defaults(fn=cmd_evaluate)

    checkin = sub.add_parser("checkin")
    checkin.add_argument("--log", action="store_true", help="append the digest to checkins.log")
    checkin.set_defaults(fn=cmd_checkin)

    run_iteration = sub.add_parser("run-iteration")
    run_iteration.add_argument("--stage", type=int, required=True)
    run_iteration.add_argument("--turns", type=int, default=None)
    run_iteration.add_argument("--allow-frozen", action="store_true")
    run_iteration.set_defaults(fn=cmd_run_iteration)

    sub.add_parser(
        "tick",
        help="one autonomous heartbeat: checkin, then execute the decision (cron this)",
    ).set_defaults(fn=cmd_tick)

    sub.add_parser(
        "report", help="regenerate the HTML monitoring dashboard (report.html)"
    ).set_defaults(fn=cmd_report)

    snapshot = sub.add_parser(
        "snapshot", help="freeze current validated artifacts into data/demo/<label>/ (committed fallback)"
    )
    snapshot.add_argument("--label", required=True, help="snapshot directory name, e.g. stage1")
    snapshot.add_argument("--note", default="", help="optional human note stored in the manifest/README")
    snapshot.set_defaults(fn=cmd_snapshot)

    ns = parser.parse_args(argv)
    return ns.fn(ns)


if __name__ == "__main__":
    raise SystemExit(main())
