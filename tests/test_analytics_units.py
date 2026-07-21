"""Focused units for shared analytics math: group_summary, eta-squared, histograms."""

from __future__ import annotations

from backend.api.persona_analytics import _eta_squared, group_summary
from backend.api.session_analytics import _session_sort_key
from backend.api.stats import histogram, histogram_counts


def test_group_summary_reward_math_and_label_key() -> None:
    group = [{"reward": 1.0}, {"reward": 0.0}, {"reward": None}]

    session_shape = group_summary("Refunds", group)
    assert session_shape == {
        "label": "Refunds",
        "n": 3,
        "pass_rate": round(1.0 / 3.0, 6),
        "fail_count": 2,
    }

    persona_shape = group_summary(
        "book",
        [{"reward": 1.0, "warmth": 0.5}, {"reward": 1.0, "warmth": None}],
        label_key="final_action",
        vectors=("warmth", "missing_vector"),
    )
    assert persona_shape["final_action"] == "book"
    assert persona_shape["pass_rate"] == 1.0
    assert persona_shape["warmth"] == 0.5
    assert "missing_vector" not in persona_shape

    assert group_summary("empty", [])["pass_rate"] is None


def test_eta_squared_separates_groups() -> None:
    perfectly_separated = {"a": [0.0, 0.0, 0.0], "b": [1.0, 1.0, 1.0]}
    assert _eta_squared(perfectly_separated) == 1.0

    identical = {"a": [0.5, 0.5], "b": [0.5, 0.5]}
    assert _eta_squared(identical) in (0.0, None)

    assert _eta_squared({"a": [1.0]}) is None or isinstance(_eta_squared({"a": [1.0]}), float)


def test_session_sort_key_uses_risk_and_flags_only_as_signal_tiebreakers() -> None:
    rows = [
        {"signal": {"outlier_score": 3.0}, "risk_band": "low", "flag_count": 0},
        {"signal": {"outlier_score": 2.0}, "risk_band": "high", "flag_count": 9},
        {"signal": {"outlier_score": 3.0}, "risk_band": "high", "flag_count": 1},
        {"signal": {"outlier_score": 3.0}, "risk_band": "high", "flag_count": 4},
    ]

    ranked = sorted(rows, key=_session_sort_key, reverse=True)

    assert [row["signal"]["outlier_score"] for row in ranked] == [3.0, 3.0, 3.0, 2.0]
    assert [(row["risk_band"], row["flag_count"]) for row in ranked[:3]] == [
        ("high", 4),
        ("high", 1),
        ("low", 0),
    ]


def test_histogram_edge_cases() -> None:
    assert histogram([]) == []
    single = histogram([2.0])
    assert single == [{"bin_start": 2.0, "bin_end": 2.0, "count": 1}]
    bins = histogram([0.0, 0.5, 1.0], n_bins=2)
    assert sum(item["count"] for item in bins) == 3


def test_histogram_counts_fixed_range_clamps_out_of_range() -> None:
    counts = histogram_counts([-5.0, 0.1, 0.9, 5.0], lo=0.0, hi=1.0, n_bins=2)
    assert counts == [2, 2]
    assert histogram_counts([1.0], lo=0.0, hi=1.0, n_bins=0) == []
    # degenerate range widens instead of dividing by zero
    assert sum(histogram_counts([1.0, 1.0], lo=1.0, hi=1.0, n_bins=4)) == 2


def test_trace_scoring_records_skip_tool_call_only_assistant_turns() -> None:
    from backend.api.models import AuditTrace, AuditTurn
    from backend.api.scoring_spaces import trace_scoring_records

    turns = (
        AuditTurn(turn_id="t0", role="user", content="run the check", index=0),
        # Tool-call-only assistant turn: no visible response to score, and a
        # zero-length assistant_response span would abort the capture run.
        AuditTurn(turn_id="t1", role="assistant", content="", index=1, tool_name="check", reasoning="call the tool"),
        AuditTurn(turn_id="t2", role="tool", content="check: ok", index=2, tool_name="check"),
        AuditTurn(turn_id="t3", role="assistant", content="All good.", index=3),
    )
    trace = AuditTrace(
        trace_id="tr_1",
        session_id="tr_1",
        user_id="u",
        domain="d",
        task_id="t",
        outcome="completed",
        reward=None,
        source_model="m",
        user_model="um",
        turns=turns,
    )

    records = trace_scoring_records([trace])
    assert [record["turn_index"] for record in records] == [3]
    record = records[0]
    span = record["assistant_response"]
    assert span["char_end"] > span["char_start"]
    assert record["text"][span["char_start"] : span["char_end"]] == "All good."
    # The skipped turn still appears in the rendered conversation context.
    assert "Tool: check: ok" in record["text"]
