from __future__ import annotations

from backend.api import stats


def test_shared_stats_match_existing_behavior_contracts() -> None:
    assert stats.as_float(True) == 1.0
    assert stats.as_float("1.25") == 1.25
    assert stats.as_float("not numeric") is None
    assert stats.avg([1, "2", None, "x"]) == 1.5
    assert stats.mean([1.0, 2.0, 3.0]) == 2.0
    assert round(stats.stddev([1.0, 2.0, 3.0]), 6) == 1.0
    assert stats.quantile([0.0, 10.0], 0.25) == 2.5
    assert stats.histogram([0.0, 1.0, 2.0], n_bins=2) == [
        {"bin_start": 0.0, "bin_end": 1.0, "count": 1},
        {"bin_start": 1.0, "bin_end": 2.0, "count": 2},
    ]
    assert stats.pearson([1.0, 2.0, 3.0], [1.0, 2.0, 3.0]) == 1.0
    assert round(stats.cohen_d([2.0, 3.0], [0.0, 1.0]), 6) == 2.828427
