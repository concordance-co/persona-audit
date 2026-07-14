"""Unit coverage for the demo hill-climb building blocks (backend/demo)."""

from __future__ import annotations

import pytest

from factory.hillclimb import checkin, normalize, rounds, run_lock, separation, transcript_qa
from factory.hillclimb.personas import PROMPTS, TRACKS, latest_prompt, latest_prompts
from factory.hillclimb.seeds import STAGE0_SEEDS, STAGE1_SEEDS, seeds_for_stage, validate_seeds
from factory.hillclimb.state import HillClimbState, load_state, save_state


def test_personas_cover_all_tracks_with_distinct_prompts():
    prompts = latest_prompts()
    assert set(prompts) == set(TRACKS)
    assert prompts["control"].system_prompt == "You are a helpful assistant."
    assert "Sol" in prompts["sol"].system_prompt
    assert "Marrow" in prompts["marrow"].system_prompt
    assert len({p.system_prompt for p in prompts.values()}) == 3
    for prompt_id, prompt in PROMPTS.items():
        assert prompt.prompt_id == prompt_id
        assert latest_prompt(prompt.track).version >= prompt.version


def test_stage_seed_sets_are_valid():
    assert validate_seeds(STAGE0_SEEDS) == []
    assert validate_seeds(STAGE1_SEEDS) == []
    assert len(seeds_for_stage(0)) == 1
    assert len(seeds_for_stage(1)) == 5
    tiers = {seed.sensitivity_tier for seed in STAGE1_SEEDS}
    assert {0, 1, 2} <= tiers

    stage2 = seeds_for_stage(2)
    assert validate_seeds(stage2) == []
    assert len(stage2) == 25
    assert len({s.seed_id for s in stage2}) == 25
    assert len({s.decision_type for s in stage2}) == 25
    assert all(len(s.user_turns) >= 4 for s in stage2)
    # tier coverage across 0-2, none tier 3 (excluded from the automated loop)
    assert {seed.sensitivity_tier for seed in stage2} == {0, 1, 2}
    with pytest.raises(NotImplementedError):
        seeds_for_stage(3)


def test_round_examples_condition_only_on_own_track_history():
    prompts = latest_prompts()
    histories: rounds.Histories = {}
    turn0 = rounds.build_round_examples(STAGE0_SEEDS, prompts, histories, 0, stage=0)
    assert len(turn0) == 3
    fake_rows = [{"example_key": ex["key"], "generated_text": f"reply from {ex['labels']['track']}"} for ex in turn0]
    rounds.apply_round_results(histories, STAGE0_SEEDS, prompts, 0, fake_rows)

    turn1 = rounds.build_round_examples(STAGE0_SEEDS, prompts, histories, 1, stage=0)
    for example in turn1:
        track = example["labels"]["track"]
        assistant_msgs = [m["content"] for m in example["prompt"] if m["role"] == "assistant"]
        assert assistant_msgs == [f"reply from {track}"]
        assert example["prompt"][0]["content"] == prompts[track].system_prompt


def test_apply_round_results_fails_loudly_on_gaps():
    prompts = latest_prompts()
    with pytest.raises(KeyError):
        rounds.apply_round_results({}, STAGE0_SEEDS, prompts, 0, [])
    empty_rows = [
        {"example_key": rounds.example_key(STAGE0_SEEDS[0].seed_id, track, 0), "generated_text": " "}
        for track in TRACKS
    ]
    with pytest.raises(ValueError):
        rounds.apply_round_results({}, STAGE0_SEEDS, prompts, 0, empty_rows)


def test_histories_json_round_trip():
    histories: rounds.Histories = {("seed_a", "sol"): ["one", "two"], ("seed_a", "marrow"): ["x"]}
    assert rounds.histories_from_json(rounds.histories_to_json(histories)) == histories


SOL_TURNS = [
    "You already know what you want. You want him to be direct. Tell him this week. That is the true next step.",
    "You want to leave. You said it yourself. Do the thing you already decided and send the email in the morning.",
]

MARROW_TURNS = [
    "There is a weight in how you describe the waiting, something that sounds heavier than the decision itself, and yet you keep returning to the door you have not walked through. I might be wrong, but I wonder whether the question underneath is not what he will say, and yet something older, something about what happens to you when an answer finally arrives. What do you notice in your body when you imagine asking, and what part of you goes quiet just then, as if it already knows the room it would have to enter?",
    "Something in the way you tell this story leaves you out of it almost entirely, and yet the current of it keeps pulling toward a thread you have not named. I could be wrong, and part of me wonders whether the tiredness you mention might be less about the job and more about carrying a shadow of a decision you made long before this week. If we slow this down and let it breathe beneath the surface, where does your attention drift first, and what does it pass over on the way?",
]


def test_transcript_qa_passes_on_intended_contrast():
    report = transcript_qa.qa_report({"sol": SOL_TURNS, "marrow": MARROW_TURNS, "control": ["Okay."]})
    failing = [check["name"] for check in report["checks"] if not check["passed"]]
    assert report["passed"], f"unexpected failures: {failing}"


def test_transcript_qa_flags_mushy_sol():
    mushy = ["Maybe you could sit with it and explore what feels right? Perhaps it seems unclear."]
    report = transcript_qa.qa_report({"sol": mushy, "marrow": MARROW_TURNS, "control": []})
    assert not report["passed"]
    assert report["failing_tracks"] == ["sol"]


def test_transcript_qa_tolerates_occasional_literal_forbidden_words():
    # One literal "weight" in ten declarative turns is not persona leakage.
    turns = ["You will lift the weight. Do it now."] + [SOL_TURNS[0]] * 9
    report = transcript_qa.qa_report({"sol": turns, "marrow": MARROW_TURNS, "control": []})
    check = next(c for c in report["checks"] if c["name"] == "sol_forbidden_lexicon")
    assert check["passed"], check["value"]
    # Systematic leakage still fails.
    leaky = ["You will lift the weight behind the door. Do it now."] * 10
    report = transcript_qa.qa_report({"sol": leaky, "marrow": MARROW_TURNS, "control": []})
    check = next(c for c in report["checks"] if c["name"] == "sol_forbidden_lexicon")
    assert not check["passed"]


def test_normalize_round_trip(tmp_path):
    prompts = latest_prompts()
    histories: rounds.Histories = {(STAGE0_SEEDS[0].seed_id, track): [f"{track} t0", f"{track} t1"] for track in TRACKS}
    traces = normalize.traces_from_histories(STAGE0_SEEDS, prompts, histories, generation_params={"temperature": 0.45})
    assert len(traces) == 3
    for trace in traces:
        assert [turn.role for turn in trace.turns] == ["user", "assistant", "user", "assistant"]
        assert trace.labels["paired_group_id"] == STAGE0_SEEDS[0].seed_id
        assert trace.labels["track"] in TRACKS
    path = tmp_path / "traces.json"
    normalize.save_traces(traces, path)
    loaded = normalize.load_traces(path)
    assert [t.trace_id for t in loaded] == [t.trace_id for t in traces]
    assert loaded[0].turns == traces[0].turns


def _synthetic_rows(n_groups: int = 12) -> list[dict]:
    rows = []
    offsets = {"sol": 1.0, "marrow": -1.0, "control": 0.0}
    for group in range(n_groups):
        noise = (group % 5) * 0.03
        for track, offset in offsets.items():
            for surface in ("surface_a", "surface_b", "surface_c"):
                rows.append(
                    {
                        "group": f"g{group}",
                        "track": track,
                        "surface": surface,
                        "value": offset + noise,
                        "length": 100.0,
                    }
                )
            # A surface that only encodes response length.
            length = 40.0 if track == "sol" else 140.0
            rows.append(
                {
                    "group": f"g{group}",
                    "track": track,
                    "surface": "surface_lengthy",
                    "value": length / 100.0 + noise,
                    "length": length,
                }
            )
    return rows


def test_separation_report_gates_and_confounds():
    report = separation.separation_report(_synthetic_rows())
    assert report["passed"], report["reasons"]
    assert report["objective"] > separation.DEFAULT_GATES["min_objective_d"]
    assert "surface_lengthy" in report["confounded_surfaces"]
    assert "surface_lengthy" not in report["top_surfaces"]
    assert set(report["separated_surfaces"]) == {"surface_a", "surface_b", "surface_c"}


def test_separation_fails_without_contrast():
    rows = [
        {"group": f"g{i}", "track": track, "surface": "surface_a", "value": 0.5, "length": None}
        for i in range(6)
        for track in ("sol", "marrow", "control")
    ]
    report = separation.separation_report(rows)
    assert not report["passed"]
    assert report["objective"] == 0.0


def test_score_artifact_rows_use_example_key_and_coordinate_surface():
    rows = separation.rows_from_score_artifact(
        {
            "rows": [
                {
                    "coordinate": "assistant_axis_trait__calm",
                    "example_key": "seed_synth_0001__marrow__assistant_000",
                    "layer": 40,
                    "role": "assistant",
                    "score": 1.25,
                    "slice_index": 1,
                    "slice_token_count": 1,
                }
            ]
        },
        surface_prefix="score_assistant_axis.",
    )

    assert rows == [
        {
            "surface": "score_assistant_axis.assistant_axis_trait__calm.score",
            "value": 1.25,
            "track": "marrow",
            "group": "seed_synth_0001__assistant_000",
            "length": None,
        }
    ]


def test_score_artifact_rows_join_lengths_by_assistant_turn():
    rows = separation.rows_from_score_artifact(
        {
            "rows": [
                {
                    "emotion": "hurt",
                    "example_key": "seed_synth_0001__sol__assistant_002",
                    "score": 0.5,
                }
            ]
        },
        surface_prefix="score_emotions.",
        lengths={("seed_synth_0001__sol", 2): 21.0},
    )
    assert rows[0]["length"] == 21.0


def _iterated_state(objectives: list[float], *, passed: bool = False, qa_passed: bool | None = None) -> HillClimbState:
    state = HillClimbState()
    for objective in objectives:
        state.iteration += 1
        state.record_iteration(
            {
                "objective": objective,
                "separation_passed": passed,
                "qa_passed": qa_passed,
                "prompt_ids": dict(state.prompt_ids),
            }
        )
    return state


def test_checkin_bootstrap_and_frozen():
    fresh = checkin.decide(HillClimbState(), has_transcripts=False, has_separation=False)
    assert fresh["action"] == "RUN_ITERATION"
    assert "--stage 0" in fresh["command"]
    frozen = HillClimbState(frozen=True)
    assert checkin.decide(frozen, has_transcripts=True, has_separation=True)["action"] == "HOLD_HUMAN"


def test_checkin_waits_on_active_run():
    decision = checkin.decide(
        HillClimbState(),
        has_transcripts=False,
        has_separation=False,
        active_run={"pid": 123, "command": "run-iteration --stage 1", "started_at": "now"},
    )

    assert decision["action"] == "WAIT_RUNNING"
    assert decision["command"] is None


def test_checkin_holds_on_stale_active_run():
    decision = checkin.decide(
        HillClimbState(),
        has_transcripts=False,
        has_separation=False,
        active_run={"stale": True, "reason": "pid 123 is not running", "path": "active_run.json"},
    )

    assert decision["action"] == "HOLD_HUMAN"
    assert "stale active-run lock" in decision["reason"]


def test_checkin_untested_prompt_bump_reruns_current_stage():
    state = _iterated_state([0.3])
    state.prompt_ids["sol"] = "sol_v2"
    decision = checkin.decide(state, has_transcripts=True, has_separation=True)
    assert decision["action"] == "RUN_ITERATION"
    assert "--stage 0" in decision["command"]


def test_checkin_pass_advances_and_stage1_gate_depends_on_seeds():
    stage0 = _iterated_state([0.9], passed=True, qa_passed=True)
    decision = checkin.decide(stage0, has_transcripts=True, has_separation=True)
    assert decision["action"] == "RUN_ITERATION" and "--stage 1" in decision["command"]
    # Stage 1 pass holds while Stage 2 seeds are missing...
    stage1 = _iterated_state([0.9], passed=True, qa_passed=True)
    stage1.stage = 1
    assert checkin.decide(stage1, has_transcripts=True, has_separation=True)["action"] == "HOLD_HUMAN"
    # ...and auto-advances to Stage 2 once they are registered.
    advanced = checkin.decide(stage1, has_transcripts=True, has_separation=True, stage2_seeds_ready=True)
    assert advanced["action"] == "RUN_ITERATION" and "--stage 2" in advanced["command"]


def test_checkin_separation_pass_with_qa_fail_escalates_instead_of_advancing():
    state = _iterated_state([0.9], passed=True, qa_passed=False)
    decision = checkin.decide(state, has_transcripts=True, has_separation=True, qa_failing_tracks=["marrow"])
    assert decision["action"] == "ESCALATE_PROMPT"
    assert "marrow" in decision["reason"]


def test_checkin_escalates_on_stall_and_names_qa_track():
    stalled = _iterated_state([0.5, 0.4, 0.3])
    decision = checkin.decide(stalled, has_transcripts=True, has_separation=True)
    assert decision["action"] == "ESCALATE_PROMPT"
    assert "not improved" in decision["reason"]
    failing = _iterated_state([0.4])
    decision = checkin.decide(failing, has_transcripts=True, has_separation=True, qa_failing_tracks=["marrow"])
    assert decision["action"] == "ESCALATE_PROMPT"
    assert "marrow" in decision["reason"]


def test_checkin_digest_compacts_long_surface_lists():
    state = _iterated_state([1.0], passed=True)
    text = checkin.render_markdown(
        state,
        {"action": "RUN_ITERATION", "reason": "go", "command": "run"},
        separation={
            "passed": True,
            "objective": 1.0,
            "separated_surfaces": [f"surface_{i}" for i in range(20)],
            "top_surfaces": [f"top_{i}" for i in range(10)],
            "confounded_surfaces": [],
            "reasons": [],
        },
    )

    assert "surface_19" not in text
    assert "(+12 more)" in text
    assert "top_9" not in text
    assert "(+2 more)" in text


def test_state_round_trip_and_best_tracking(tmp_path):
    state = HillClimbState()
    state.iteration = 1
    state.record_iteration({"objective": 0.4})
    state.iteration = 2
    state.record_iteration({"objective": 0.9})
    state.iteration = 3
    state.record_iteration({"objective": 0.6})
    assert state.best_objective == 0.9
    assert state.best_iteration == 2
    path = tmp_path / "state.json"
    save_state(state, path)
    loaded = load_state(path)
    assert loaded.best_iteration == 2
    assert len(loaded.history) == 3
    assert loaded.prompt_ids["sol"] == "sol_v1"


def test_state_record_iteration_replaces_existing_iteration():
    state = HillClimbState()
    state.iteration = 1
    state.record_iteration({"objective": 0.1, "separation_passed": False})
    state.record_iteration({"objective": 0.9, "separation_passed": True})

    assert len(state.history) == 1
    assert state.history[0]["objective"] == 0.9
    assert state.best_objective == 0.9


def test_tick_escalation_requires_configured_escalator(tmp_path, monkeypatch):
    from factory.scripts import demo_hillclimb as driver

    state = HillClimbState()
    state.iteration = 3
    marker_path = tmp_path / "last_escalation.json"
    monkeypatch.setattr(driver, "ESCALATION_MARKER_PATH", marker_path)
    monkeypatch.delenv(driver.ESCALATOR_CMD_ENV, raising=False)
    assert driver._escalate_prompt(state, "reason") == 3
    assert not marker_path.exists()


def test_tick_escalates_once_per_iteration_and_detects_prompt_bump(tmp_path, monkeypatch):
    from factory.scripts import demo_hillclimb as driver

    state = HillClimbState()
    state.iteration = 3
    marker_path = tmp_path / "last_escalation.json"
    monkeypatch.setattr(driver, "ESCALATION_MARKER_PATH", marker_path)

    # A no-op escalator writes the marker but changes no prompts -> needs human.
    monkeypatch.setenv(driver.ESCALATOR_CMD_ENV, "true")
    monkeypatch.setattr(driver, "load_state", lambda: state)
    assert driver._escalate_prompt(state, "stalled") == 3
    assert marker_path.exists()

    # Same (iteration, prompts) never re-launches: a broken command would raise
    # FileNotFoundError if the guard failed to short-circuit.
    monkeypatch.setenv(driver.ESCALATOR_CMD_ENV, "definitely-not-a-command")
    assert driver._escalate_prompt(state, "stalled") == 3

    # An escalator that bumps prompt_ids counts as success; next tick runs it.
    bumped = HillClimbState()
    bumped.iteration = 3
    bumped.prompt_ids = {**dict(bumped.prompt_ids), "marrow": "marrow_v2"}
    monkeypatch.setenv(driver.ESCALATOR_CMD_ENV, "true")
    monkeypatch.setattr(driver, "load_state", lambda: bumped)
    fresh_state = HillClimbState()
    fresh_state.iteration = 4
    assert driver._escalate_prompt(fresh_state, "stalled") == 0


def test_run_lock_reports_live_and_clears(tmp_path):
    path = tmp_path / "active_run.json"

    with run_lock.run_lock({"command": "run-iteration --stage 1"}, path=path):
        active = run_lock.active_run(path)
        assert active is not None
        assert active["stale"] is False
        assert active["command"] == "run-iteration --stage 1"

    assert run_lock.active_run(path) is None
