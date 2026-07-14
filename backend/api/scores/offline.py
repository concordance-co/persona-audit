"""Offline score access: the bundled supplemental-score JSON path (no database).

Offline twin of backend.api.scores.sql_summaries — the ``_supplemental_X``
aggregations here mirror the SQL ``_summary_X`` builders and must keep the
same output shapes. Numeric primitives come from backend.api.cache import data_cache
from backend.api.stats.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Any

from backend.api.cache import data_cache
from backend.api.scores.shaping import (
    IMPORTANT_DYNAMIC_COORDINATES,
    _coordinate_bands_from_summary,
    _coordinate_stats_from_summary,
    _projection_tail_thresholds_from_summary,
    _tail_explorer_from_summary,
)
from backend.api.stats import mean as _stats_mean
from backend.api.stats import pearson as _stats_pearson
from backend.api.stats import quantile as _stats_quantile
from backend.paths import DATA_ROOT

SUPPLEMENTAL_SCORE_DIR = DATA_ROOT / "supplemental_scores"


def _stats_pearson_unrounded(xs, ys):
    return _stats_pearson(xs, ys, ndigits=None)


@data_cache(maxsize=4)
def _supplemental_score_rows(run_id: str) -> tuple[dict[str, Any], ...]:
    path = SUPPLEMENTAL_SCORE_DIR / f"{run_id}_assistant_trait_scores.json"
    if not path.exists():
        return ()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return ()
    if str(payload.get("run_id") or "") != run_id:
        return ()
    rows = payload.get("rows")
    if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes)):
        return ()
    return tuple(dict(row) for row in rows if isinstance(row, Mapping))


def _supplemental_score_rows_for_trace(trace_id: str, run_id: str) -> list[dict[str, Any]]:
    return [dict(row) for row in _supplemental_score_rows(run_id) if str(row.get("trace_id") or "") == str(trace_id)]


def _supplemental_score_rows_for_coordinates(coordinates: Sequence[str], run_id: str) -> list[dict[str, Any]]:
    selected = {str(coordinate) for coordinate in coordinates}
    return [
        _coordinate_projection_row(row)
        for row in _supplemental_score_rows(run_id)
        if str(row.get("coordinate") or "") in selected and row.get("score") is not None
    ]


def _append_missing_supplemental_rows(
    rows: Sequence[Mapping[str, Any]],
    supplemental_rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    merged = [dict(row) for row in rows]
    seen = {_score_row_identity(row) for row in merged}
    for row in supplemental_rows:
        key = _score_row_identity(row)
        if key in seen:
            continue
        merged.append(dict(row))
        seen.add(key)
    return merged


def _score_row_identity(row: Mapping[str, Any]) -> tuple[Any, ...]:
    return (
        row.get("score_family"),
        row.get("coordinate"),
        row.get("example_key"),
        row.get("trace_id"),
        row.get("turn_index"),
        row.get("layer"),
        row.get("metric"),
        row.get("score"),
    )


def _coordinate_projection_row(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "score_family": row.get("score_family"),
        "coordinate": row.get("coordinate"),
        "trace_id": row.get("trace_id"),
        "turn_index": row.get("turn_index"),
        "task_id": row.get("task_id"),
        "outcome": row.get("outcome"),
        "reward": row.get("reward"),
        "score": row.get("score"),
    }


def _merge_supplemental_inventory(inventory: Mapping[str, Any], rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    merged = dict(inventory)
    families = [dict(row) for row in merged.get("families", []) if isinstance(row, Mapping)]
    if not rows:
        merged["families"] = families
        return merged
    by_family: dict[str, dict[str, set[str] | int]] = {}
    for row in rows:
        family = str(row.get("score_family") or "unknown")
        bucket = by_family.setdefault(family, {"coordinates": set(), "row_count": 0})
        coordinates = bucket["coordinates"]
        if isinstance(coordinates, set) and row.get("coordinate"):
            coordinates.add(str(row["coordinate"]))
        bucket["row_count"] = int(bucket["row_count"]) + 1
    for family, bucket in by_family.items():
        coordinates = bucket["coordinates"]
        families.append(
            {
                "score_family": f"{family}_supplemental",
                "coordinate_count": len(coordinates) if isinstance(coordinates, set) else 0,
                "row_count": int(bucket["row_count"]),
            }
        )
    merged["available"] = True
    merged["families"] = families
    return merged


def _merge_supplemental_score_surface(surface: Mapping[str, Any], rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    merged = dict(surface)
    if not rows:
        return merged
    stats = _supplemental_tail_stats(rows)
    histograms = _supplemental_tail_histograms(rows)
    tail_rows = _supplemental_tail_rows(rows)
    dynamics = _supplemental_conversation_dynamics(rows)
    thresholds = _projection_tail_thresholds_from_summary(stats)
    merged["available"] = True
    merged["assistant_traits"] = _merge_coordinate_rows(
        merged.get("assistant_traits", []),
        _coordinate_stats_from_summary(stats, score_family="assistant_axis"),
    )
    merged["assistant_trait_bands"] = _merge_coordinate_rows(
        merged.get("assistant_trait_bands", []),
        _coordinate_bands_from_summary(
            stats,
            score_family="assistant_axis",
            exclude_coordinates={"assistant_axis"},
        ),
    )
    merged["tail_explorer"] = _merge_coordinate_rows(
        merged.get("tail_explorer", []),
        _tail_explorer_from_summary(stats, histograms, tail_rows),
        key_fields=("score_family", "coordinate"),
    )
    merged["projection_thresholds"] = _merge_coordinate_rows(
        merged.get("projection_thresholds", []),
        thresholds,
        key_fields=("score_family", "coordinate"),
    )
    merged["conversation_dynamics"] = _merge_coordinate_rows(
        merged.get("conversation_dynamics", []),
        dynamics,
    )
    return merged


def _merge_coordinate_rows(
    existing_rows: Any,
    supplemental_rows: Sequence[Mapping[str, Any]],
    *,
    key_fields: tuple[str, ...] = ("coordinate",),
) -> list[dict[str, Any]]:
    rows = (
        [dict(row) for row in existing_rows if isinstance(row, Mapping)]
        if isinstance(existing_rows, Sequence) and not isinstance(existing_rows, (str, bytes))
        else []
    )
    by_key = {tuple(str(row.get(field) or "") for field in key_fields): index for index, row in enumerate(rows)}
    for row in supplemental_rows:
        item = dict(row)
        key = tuple(str(item.get(field) or "") for field in key_fields)
        if key in by_key:
            rows[by_key[key]] = item
        else:
            by_key[key] = len(rows)
            rows.append(item)
    return rows


def _supplemental_tail_stats(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    buckets: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        score = row.get("score")
        coordinate = str(row.get("coordinate") or "")
        family = str(row.get("score_family") or "")
        if score is None or not coordinate or not family:
            continue
        bucket = buckets.setdefault((family, coordinate), {"values": [], "pass_values": []})
        bucket["values"].append(float(score))
        outcome = str(row.get("outcome") or "")
        if outcome == "pass":
            bucket["pass_values"].append(1.0)
        elif outcome == "fail":
            bucket["pass_values"].append(0.0)
        else:
            bucket["pass_values"].append(None)
    stats: list[dict[str, Any]] = []
    for (family, coordinate), bucket in buckets.items():
        values = list(bucket["values"])
        pass_values = list(bucket["pass_values"])
        sorted_values = sorted(values)
        paired = [(value, pass_value) for value, pass_value in zip(values, pass_values) if pass_value is not None]
        stats.append(
            {
                "score_family": family,
                "coordinate": coordinate,
                "rows": len(values),
                "mean": _stats_mean(values),
                "min": sorted_values[0],
                "max": sorted_values[-1],
                "q05": _stats_quantile(sorted_values, 0.05),
                "q20": _stats_quantile(sorted_values, 0.20),
                "q40": _stats_quantile(sorted_values, 0.40),
                "q50": _stats_quantile(sorted_values, 0.50),
                "q60": _stats_quantile(sorted_values, 0.60),
                "q80": _stats_quantile(sorted_values, 0.80),
                "q95": _stats_quantile(sorted_values, 0.95),
                "pass_correlation": _stats_pearson_unrounded(
                    [item[0] for item in paired],
                    [item[1] for item in paired],
                ),
                "outcome_rows": len(paired),
            }
        )
    return stats


def _supplemental_tail_histograms(rows: Sequence[Mapping[str, Any]], *, n_bins: int = 18) -> list[dict[str, Any]]:
    values_by_key: dict[tuple[str, str], list[Mapping[str, Any]]] = {}
    for row in rows:
        if row.get("score") is None:
            continue
        key = (str(row.get("score_family") or ""), str(row.get("coordinate") or ""))
        if not all(key):
            continue
        values_by_key.setdefault(key, []).append(row)
    histograms: list[dict[str, Any]] = []
    for (family, coordinate), group in values_by_key.items():
        values = [float(row["score"]) for row in group]
        lo = min(values)
        hi = max(values)
        bins: dict[int, dict[str, int]] = {}
        for row in group:
            value = float(row["score"])
            index = 0 if hi == lo else min(n_bins - 1, int(((value - lo) / (hi - lo)) * n_bins))
            bucket = bins.setdefault(index, {"count": 0, "pass_count": 0, "fail_count": 0})
            bucket["count"] += 1
            if row.get("outcome") == "pass":
                bucket["pass_count"] += 1
            elif row.get("outcome") == "fail":
                bucket["fail_count"] += 1
        for index, bucket in bins.items():
            histograms.append(
                {
                    "score_family": family,
                    "coordinate": coordinate,
                    "lo": lo,
                    "hi": hi,
                    "bin": index,
                    "count": bucket["count"],
                    "pass_count": bucket["pass_count"],
                    "fail_count": bucket["fail_count"],
                }
            )
    return histograms


def _supplemental_tail_rows(rows: Sequence[Mapping[str, Any]], *, n_tail: int = 10) -> list[dict[str, Any]]:
    by_key: dict[tuple[str, str], list[Mapping[str, Any]]] = {}
    for row in rows:
        if row.get("score") is None:
            continue
        key = (str(row.get("score_family") or ""), str(row.get("coordinate") or ""))
        if all(key):
            by_key.setdefault(key, []).append(row)
    tail_rows: list[dict[str, Any]] = []
    for (family, coordinate), group in by_key.items():
        positive = sorted(group, key=lambda row: float(row["score"]), reverse=True)
        negative = sorted(group, key=lambda row: float(row["score"]))
        ranks: dict[tuple[str, Any], dict[str, int]] = {}
        for index, row in enumerate(positive[:n_tail], start=1):
            ranks.setdefault((str(row.get("example_key") or ""), row.get("turn_index")), {})["positive_rank"] = index
        for index, row in enumerate(negative[:n_tail], start=1):
            ranks.setdefault((str(row.get("example_key") or ""), row.get("turn_index")), {})["negative_rank"] = index
        for row in list(positive[:n_tail]) + list(negative[:n_tail]):
            rank = ranks.get((str(row.get("example_key") or ""), row.get("turn_index")), {})
            tail_rows.append(
                {
                    "score_family": family,
                    "coordinate": coordinate,
                    "trace_id": row.get("trace_id"),
                    "turn_index": row.get("turn_index"),
                    "value": float(row["score"]),
                    "domain": row.get("domain"),
                    "task_id": row.get("task_id"),
                    "outcome": row.get("outcome"),
                    "reward": row.get("reward"),
                    "role": row.get("role"),
                    "summary": row.get("summary"),
                    "positive_rank": rank.get("positive_rank", n_tail + 1),
                    "negative_rank": rank.get("negative_rank", n_tail + 1),
                }
            )
    return tail_rows


def _supplemental_conversation_dynamics(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    max_turn: dict[str, int] = {}
    for row in rows:
        trace_id = str(row.get("trace_id") or "")
        turn_index = row.get("turn_index")
        if not trace_id or turn_index is None:
            continue
        max_turn[trace_id] = max(max_turn.get(trace_id, 0), int(turn_index))
    grouped: dict[str, dict[str, list[float]]] = {}
    for row in rows:
        coordinate = str(row.get("coordinate") or "")
        trace_id = str(row.get("trace_id") or "")
        score = row.get("score")
        turn_index = row.get("turn_index")
        if coordinate not in IMPORTANT_DYNAMIC_COORDINATES or not trace_id or score is None or turn_index is None:
            continue
        ratio = int(turn_index) / max(max_turn.get(trace_id, 0), 1)
        segment = "early" if ratio <= 0.33 else "mid" if ratio <= 0.67 else "late"
        grouped.setdefault(coordinate, {}).setdefault(segment, []).append(float(score))
    dynamics: list[dict[str, Any]] = []
    for coordinate, segments in grouped.items():
        if not segments.get("early") or not segments.get("late"):
            continue
        early = _stats_mean(segments["early"])
        late = _stats_mean(segments["late"])
        dynamics.append(
            {
                "coordinate": coordinate,
                "early": round(early, 6),
                "mid": round(_stats_mean(segments["mid"]), 6) if segments.get("mid") else None,
                "late": round(late, 6),
                "delta": round(late - early, 6),
                "rows": sum(len(values) for values in segments.values()),
            }
        )
    dynamics.sort(key=lambda row: abs(float(row["delta"])), reverse=True)
    return dynamics
