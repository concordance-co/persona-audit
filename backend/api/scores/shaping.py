"""Row -> view-model shaping shared by the SQL and offline score paths.

Both backend.api.scores.sql_summaries (Postgres) and backend.api.scores.offline
(bundled JSON) produce the same summary shapes; the helpers here turn their raw
rows into the payload fragments the dashboard renders. Keep them path-agnostic.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from typing import Any


def _pass_correlation_sort_value(row: Mapping[str, Any]) -> float:
    value = row.get("pass_correlation")
    return abs(float(value)) if value is not None else -1.0


def _coordinate_stats_from_summary(
    rows: Sequence[Mapping[str, Any]],
    *,
    score_family: str,
    include_coordinates: set[str] | None = None,
    sort_by_pass_correlation: bool = False,
) -> list[dict[str, Any]]:
    stats: list[dict[str, Any]] = []
    for row in rows:
        if row.get("score_family") != score_family:
            continue
        if include_coordinates is not None and str(row.get("coordinate")) not in include_coordinates:
            continue
        item = {
            "coordinate": str(row["coordinate"]),
            "mean": _rounded_float(row["mean"]),
            "min": _round_or_none(row["min"]),
            "max": _round_or_none(row["max"]),
            "rows": int(row["rows"]),
        }
        item.update(_surface_row_metadata(row))
        stats.append(item)
    stats.sort(
        key=lambda row: _pass_correlation_sort_value(row) if sort_by_pass_correlation else abs(float(row["mean"])),
        reverse=True,
    )
    return stats


def _coordinate_bands_from_summary(
    rows: Sequence[Mapping[str, Any]],
    *,
    score_family: str,
    exclude_coordinates: set[str] | None = None,
    sort_by_pass_correlation: bool = False,
) -> list[dict[str, Any]]:
    exclude_coordinates = exclude_coordinates or set()
    boundaries: list[dict[str, Any]] = []
    for row in rows:
        coordinate = str(row.get("coordinate") or "")
        if row.get("score_family") != score_family or coordinate in exclude_coordinates:
            continue
        q20 = _rounded_float(row["q20"])
        q40 = _rounded_float(row["q40"])
        q60 = _rounded_float(row["q60"])
        q80 = _rounded_float(row["q80"])
        row_min = _rounded_float(row["min"])
        row_max = _rounded_float(row["max"])
        boundaries.append(
            {
                "coordinate": coordinate,
                "rows": int(row["rows"]),
                "mean": _rounded_float(row["mean"]),
                "min": row_min,
                "q20": q20,
                "q40": q40,
                "q60": q60,
                "q80": q80,
                "max": row_max,
                "bands": {
                    "A": {"min": q80, "max": row_max},
                    "B": {"min": q60, "max": q80},
                    "C": {"min": q40, "max": q60},
                    "D": {"min": q20, "max": q40},
                    "E": {"min": row_min, "max": q20},
                },
                **_surface_row_metadata(row),
            }
        )
    boundaries.sort(
        key=lambda row: _pass_correlation_sort_value(row) if sort_by_pass_correlation else abs(float(row["mean"])),
        reverse=True,
    )
    return boundaries


def _tail_explorer_from_summary(
    stats: Sequence[Mapping[str, Any]],
    histogram_rows: Sequence[Mapping[str, Any]],
    tail_rows: Sequence[Mapping[str, Any]],
    *,
    n_bins: int = 18,
    n_tail: int = 10,
) -> list[dict[str, Any]]:
    histograms: dict[tuple[str, str], list[dict[str, Any]]] = {}
    hist_counts: dict[tuple[str, str], dict[int, dict[str, int]]] = {}
    hist_ranges: dict[tuple[str, str], tuple[float, float]] = {}
    for row in histogram_rows:
        key = (str(row["score_family"]), str(row["coordinate"]))
        hist_counts.setdefault(key, {})[int(row["bin"])] = {
            "count": int(row["count"]),
            "pass_count": int(row.get("pass_count") or 0),
            "fail_count": int(row.get("fail_count") or 0),
        }
        hist_ranges[key] = (float(row["lo"]), float(row["hi"]))
    for key, counts in hist_counts.items():
        lo, hi = hist_ranges[key]
        if lo == hi:
            histograms[key] = [
                {
                    "bin_start": round(lo, 6),
                    "bin_end": round(hi, 6),
                    "count": sum(bucket["count"] for bucket in counts.values()),
                    "pass_count": sum(bucket["pass_count"] for bucket in counts.values()),
                    "fail_count": sum(bucket["fail_count"] for bucket in counts.values()),
                }
            ]
            continue
        step = (hi - lo) / n_bins
        histograms[key] = [
            {
                "bin_start": round(lo + index * step, 6),
                "bin_end": round(lo + (index + 1) * step, 6),
                "count": counts.get(index, {}).get("count", 0),
                "pass_count": counts.get(index, {}).get("pass_count", 0),
                "fail_count": counts.get(index, {}).get("fail_count", 0),
            }
            for index in range(n_bins)
        ]

    positive_rows: dict[tuple[str, str], list[Mapping[str, Any]]] = {}
    negative_rows: dict[tuple[str, str], list[Mapping[str, Any]]] = {}
    for row in tail_rows:
        key = (str(row["score_family"]), str(row["coordinate"]))
        if int(row["positive_rank"]) <= n_tail:
            positive_rows.setdefault(key, []).append(row)
        if int(row["negative_rank"]) <= n_tail:
            negative_rows.setdefault(key, []).append(row)

    surfaces: list[dict[str, Any]] = []
    for row in stats:
        key = (str(row["score_family"]), str(row["coordinate"]))
        surfaces.append(
            {
                "score_family": key[0],
                "coordinate": key[1],
                "rows": int(row["rows"]),
                "mean": _rounded_float(row["mean"]),
                "min": _round_or_none(row["min"]),
                "max": _round_or_none(row["max"]),
                "q05": _round_or_none(row["q05"]),
                "q50": _round_or_none(row["q50"]),
                "q95": _round_or_none(row["q95"]),
                "histogram": histograms.get(key, []),
                "positive_tail": [
                    _tail_item(item, float(item["value"]))
                    for item in sorted(positive_rows.get(key, []), key=lambda item: int(item["positive_rank"]))[:n_tail]
                ],
                "negative_tail": [
                    _tail_item(item, float(item["value"]))
                    for item in sorted(negative_rows.get(key, []), key=lambda item: int(item["negative_rank"]))[:n_tail]
                ],
                **_surface_row_metadata(row),
            }
        )
    surfaces.sort(key=lambda row: (str(row["score_family"]), -abs(float(row["mean"])), str(row["coordinate"])))
    return surfaces


def _float_or_none(value: Any) -> float | None:
    if value is None:
        return None
    return float(value)


def _rounded_float(value: Any) -> float:
    return round(float(value), 6)


def _round_or_none(value: Any) -> float | None:
    return None if value is None else _rounded_float(value)


def _surface_row_metadata(row: Mapping[str, Any]) -> dict[str, Any]:
    metadata: dict[str, Any] = {}
    for key in (
        "cluster",
        "members",
        "member_coordinates",
        "member_count",
        "min_matched_members",
        "max_matched_members",
        "pass_correlation",
        "outcome_rows",
    ):
        value = row.get(key)
        if value is not None:
            metadata[key] = value
    return metadata


def _module_score(module: str, trace_id: str, score: float | None, metric: str) -> dict[str, Any] | None:
    if score is None:
        return None
    return {
        "module": module,
        "trace_id": trace_id,
        "scorer_model": "persona_audit_activation_scores",
        "score": round(float(score), 6),
        "band": _score_band(float(score)),
        "confidence": 0.85,
        "metric": metric,
    }


def _high_stakes_probability(row: Mapping[str, Any]) -> float | None:
    payload = row.get("row_payload")
    by_class = payload.get("probability_by_class") if isinstance(payload, Mapping) else None
    if isinstance(by_class, Mapping) and "high-stakes" in by_class:
        return float(by_class["high-stakes"])
    probability = row.get("probability")
    if probability is not None and row.get("positive_class") == "low-stakes":
        return 1.0 - float(probability)
    if probability is not None:
        return float(probability)
    return None


def _coordinate_stats(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    buckets: dict[str, dict[str, Any]] = {}
    for row in rows:
        coordinate = str(row.get("coordinate") or "")
        score = row.get("score")
        if not coordinate or score is None:
            continue
        bucket = buckets.setdefault(
            coordinate, {"coordinate": coordinate, "sum": 0.0, "n": 0, "min": None, "max": None}
        )
        value = float(score)
        bucket["sum"] += value
        bucket["n"] += 1
        bucket["min"] = value if bucket["min"] is None else min(float(bucket["min"]), value)
        bucket["max"] = value if bucket["max"] is None else max(float(bucket["max"]), value)
    stats = [
        {
            "coordinate": bucket["coordinate"],
            "mean": round(float(bucket["sum"]) / max(int(bucket["n"]), 1), 6),
            "min": round(float(bucket["min"]), 6) if bucket["min"] is not None else None,
            "max": round(float(bucket["max"]), 6) if bucket["max"] is not None else None,
            "rows": int(bucket["n"]),
        }
        for bucket in buckets.values()
    ]
    stats.sort(key=lambda row: abs(float(row["mean"])), reverse=True)
    return stats


def _projection_tail_thresholds_from_summary(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    thresholds: list[dict[str, Any]] = []
    for row in rows:
        score_family = str(row.get("score_family") or "")
        coordinate = str(row.get("coordinate") or "")
        q20 = row.get("q20")
        q80 = row.get("q80")
        if not score_family or not coordinate or q20 is None or q80 is None:
            continue
        thresholds.append(
            {
                "score_family": score_family,
                "coordinate": coordinate,
                "rows": int(row.get("rows") or 0),
                "q20": _rounded_float(q20),
                "q80": _rounded_float(q80),
            }
        )
    thresholds.sort(key=lambda row: (str(row["score_family"]), str(row["coordinate"])))
    return thresholds


def _high_stakes_probe_stats(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    buckets: dict[str, dict[str, Any]] = {}
    for row in rows:
        if row.get("score_family") != "high_stakes":
            continue
        coordinate = str(row.get("coordinate") or "")
        probability = _high_stakes_probability(row)
        if not coordinate or probability is None:
            continue
        bucket = buckets.setdefault(
            coordinate,
            {
                "coordinate": coordinate,
                "sum_probability": 0.0,
                "rows": 0,
                "high_count": 0,
                "predictions": {},
            },
        )
        bucket["sum_probability"] += probability
        bucket["rows"] += 1
        if probability >= 0.5:
            bucket["high_count"] += 1
        prediction = str(row.get("prediction") or "")
        if prediction:
            bucket["predictions"][prediction] = bucket["predictions"].get(prediction, 0) + 1
    stats = [
        {
            "coordinate": bucket["coordinate"],
            "mean_high_stakes_probability": round(float(bucket["sum_probability"]) / max(int(bucket["rows"]), 1), 6),
            "high_stakes_rate": round(float(bucket["high_count"]) / max(int(bucket["rows"]), 1), 6),
            "rows": int(bucket["rows"]),
            "predictions": dict(bucket["predictions"]),
        }
        for bucket in buckets.values()
    ]
    stats.sort(key=lambda row: float(row["mean_high_stakes_probability"]), reverse=True)
    return stats


IMPORTANT_DYNAMIC_COORDINATES = {
    "assistant_axis_trait__confident",
    "assistant_axis_trait__assertive",
    "assistant_axis_trait__decisive",
    "assistant_axis_trait__cautious",
    "assistant_axis_trait__conciliatory",
    "assistant_axis_trait__manipulative",
    "assistant_axis_trait__sycophantic",
    "assistant_axis_trait__technical",
    "assistant_axis_trait__calm",
    "assistant_axis_trait__supportive",
    "emotion__inspired",
    "emotion__proud",
    "emotion__self_confident",
    "emotion__smug",
    "emotion__anxious",
    "emotion__worried",
    "emotion__frustrated",
    "emotion__calm",
    "high_stakes__finance_cfpb__domain_adapted_probe",
    "high_stakes__mt_balanced__domain_adapted_probe",
    "high_stakes__mts_balanced__domain_adapted_probe",
    "high_stakes__synthetic_test__generic_mean_probe",
}


def _tail_item(row: Mapping[str, Any], value: float) -> dict[str, Any]:
    return {
        "trace_id": row.get("trace_id"),
        "turn_index": row.get("turn_index"),
        "value": round(value, 6),
        "domain": row.get("domain"),
        "task_id": row.get("task_id"),
        "outcome": row.get("outcome"),
        "reward": row.get("reward"),
        "role": row.get("role"),
        "summary": _clip_summary(row.get("summary")),
    }


def _clip_summary(value: Any, limit: int = 180) -> str:
    text = " ".join(str(value or "").split())
    return text if len(text) <= limit else text[: limit - 1] + "..."


def _score_band(score: float) -> str:
    if score >= 0.65:
        return "high"
    if score >= 0.25:
        return "mid"
    return "low"
