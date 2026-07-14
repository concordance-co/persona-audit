"""Focused units for shared analytics math: group_summary, eta-squared, histograms."""

from __future__ import annotations

from backend.api.persona_analytics import _eta_squared, group_summary
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
