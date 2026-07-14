"""Activation-score separation metrics: the hill-climb objective and gates.

The build plan's Stage 2 gate ("surfaces separate the tracks in useful,
inspectable ways") is made quantitative here so an automated loop can climb
it:

- For each score surface, compute the paired effect size (Cohen's d over
  per-seed paired differences, pairing tracks by ``paired_group_id``).
- Objective = mean |d(sol, marrow)| over the strongest ``top_k`` surfaces.
- Guards: control must not collapse into either persona on the surfaces that
  drive the objective, and surfaces whose per-example scores just track
  response length are flagged as confounded and excluded from the objective.

Input rows are deliberately generic so any score source (Modal score
artifacts, Postgres score tables, local caches) can be adapted:
``{"group": ..., "track": ..., "surface": ..., "value": float, "length": int?}``
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from typing import Any

import numpy as np

DEFAULT_GATES: dict[str, float] = {
    # Stage 2 passes when the objective clears this bar...
    "min_objective_d": 0.8,
    # ...on at least this many surfaces individually...
    "min_separated_surfaces": 3,
    "min_surface_d": 0.8,
    # ...with control staying distinguishable from both personas there.
    "min_control_d": 0.3,
    # Surfaces more length-correlated than this are excluded as confounded.
    "max_length_correlation": 0.6,
    # How many top surfaces the objective averages over.
    "top_k": 5,
}


def _paired_values(
    rows: Sequence[Mapping[str, Any]], surface: str, track_a: str, track_b: str
) -> tuple[np.ndarray, np.ndarray]:
    by_group: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    for row in rows:
        if row["surface"] != surface:
            continue
        by_group[str(row["group"])][str(row["track"])].append(float(row["value"]))
    a_values: list[float] = []
    b_values: list[float] = []
    for group_values in by_group.values():
        if group_values.get(track_a) and group_values.get(track_b):
            a_values.append(float(np.mean(group_values[track_a])))
            b_values.append(float(np.mean(group_values[track_b])))
    return np.asarray(a_values), np.asarray(b_values)


def paired_effect_size(rows: Sequence[Mapping[str, Any]], surface: str, track_a: str, track_b: str) -> dict[str, float]:
    """Cohen's d on paired differences; sign is track_a minus track_b."""

    a_values, b_values = _paired_values(rows, surface, track_a, track_b)
    n = len(a_values)
    if n < 2:
        return {"d": 0.0, "n": float(n)}
    diffs = a_values - b_values
    std = float(np.std(diffs, ddof=1))
    if std == 0.0:
        d = 0.0 if float(np.mean(diffs)) == 0.0 else float(np.sign(np.mean(diffs))) * 10.0
    else:
        d = float(np.mean(diffs)) / std
    return {"d": d, "n": float(n)}


def length_correlation(rows: Sequence[Mapping[str, Any]], surface: str) -> float | None:
    values = [
        (float(row["value"]), float(row["length"]))
        for row in rows
        if row["surface"] == surface and row.get("length") is not None
    ]
    if len(values) < 3:
        return None
    value_arr = np.asarray([v for v, _ in values])
    length_arr = np.asarray([length for _, length in values])
    if float(np.std(value_arr)) == 0.0 or float(np.std(length_arr)) == 0.0:
        return 0.0
    return float(np.corrcoef(value_arr, length_arr)[0, 1])


def separation_report(
    rows: Sequence[Mapping[str, Any]],
    *,
    gates: Mapping[str, float] | None = None,
) -> dict[str, Any]:
    resolved_gates = {**DEFAULT_GATES, **(gates or {})}
    surfaces = sorted({str(row["surface"]) for row in rows})
    per_surface: dict[str, dict[str, Any]] = {}
    for surface in surfaces:
        sol_marrow = paired_effect_size(rows, surface, "sol", "marrow")
        sol_control = paired_effect_size(rows, surface, "sol", "control")
        marrow_control = paired_effect_size(rows, surface, "marrow", "control")
        corr = length_correlation(rows, surface)
        confounded = corr is not None and abs(corr) > resolved_gates["max_length_correlation"]
        per_surface[surface] = {
            "d_sol_marrow": sol_marrow["d"],
            "d_sol_control": sol_control["d"],
            "d_marrow_control": marrow_control["d"],
            "n_pairs": sol_marrow["n"],
            "length_correlation": corr,
            "length_confounded": confounded,
        }

    usable = {surface: stats for surface, stats in per_surface.items() if not stats["length_confounded"]}
    ranked = sorted(usable.items(), key=lambda item: abs(item[1]["d_sol_marrow"]), reverse=True)
    top = ranked[: int(resolved_gates["top_k"])]
    objective = float(np.mean([abs(stats["d_sol_marrow"]) for _, stats in top])) if top else 0.0

    separated = [
        surface
        for surface, stats in usable.items()
        if abs(stats["d_sol_marrow"]) >= resolved_gates["min_surface_d"]
        and abs(stats["d_sol_control"]) >= resolved_gates["min_control_d"]
        and abs(stats["d_marrow_control"]) >= resolved_gates["min_control_d"]
    ]

    reasons: list[str] = []
    if objective < resolved_gates["min_objective_d"]:
        reasons.append(
            f"objective {objective:.2f} < {resolved_gates['min_objective_d']} "
            f"(mean |d(sol,marrow)| over top {int(resolved_gates['top_k'])} unconfounded surfaces)"
        )
    if len(separated) < resolved_gates["min_separated_surfaces"]:
        reasons.append(
            f"only {len(separated)} surfaces fully separated "
            f"(need {int(resolved_gates['min_separated_surfaces'])} with |d|>= "
            f"{resolved_gates['min_surface_d']} and control non-collapse)"
        )
    confounded_surfaces = [s for s, stats in per_surface.items() if stats["length_confounded"]]

    return {
        "objective": objective,
        "top_surfaces": [surface for surface, _ in top],
        "separated_surfaces": separated,
        "confounded_surfaces": confounded_surfaces,
        "per_surface": per_surface,
        "gates": dict(resolved_gates),
        "passed": not reasons,
        "reasons": reasons,
    }


def rows_from_score_artifact(
    payload: Mapping[str, Any],
    *,
    surface_prefix: str = "",
    lengths: Mapping[tuple[str, int], float] | None = None,
) -> list[dict[str, Any]]:
    """Adapt a Xenon score artifact ``result.json`` into separation rows.

    Expects per-example rows carrying ``labels`` (with ``track`` and
    ``paired_group_id``, present because scoring examples set them and the
    score specs run with ``emit_labels=True``) plus numeric score fields.
    Tolerant to the exact numeric layout: every scalar numeric field that is
    not obviously bookkeeping becomes a surface. Verify against a real
    artifact on the first live run and tighten if it over-collects.

    ``lengths`` maps ``(trace_id, assistant_turn_index)`` to the length of
    that assistant turn, so the length-confound guard works even though score
    rows carry no usable length themselves (their ``slice_token_count`` is a
    constant 1 for turn-unit scores).
    """

    skip_fields = {
        "turn_index",
        "sensitivity_tier",
        "stage",
        "n",
        "index",
        "layer",
        "slice_index",
        "slice_token_count",
    }
    out: list[dict[str, Any]] = []
    for row in payload.get("rows", payload.get("records", ())) or ():
        labels = dict(row.get("labels") or {})
        track, group = _track_group_from_row(row, labels)
        if not track or not group:
            continue
        length = row.get("token_count") or labels.get("token_count")
        if length is None and lengths:
            turn_key = _assistant_turn_key(row)
            if turn_key is not None:
                length = lengths.get(turn_key)
        row_surface = _row_surface(row)
        for field_name, value in row.items():
            if field_name in {
                "labels",
                "example_key",
                "example_id",
                "coordinate",
                "emotion",
                "probe",
                "positive_class",
                "prediction",
                "role",
                "slice_name",
                "tags",
                "unit",
            }:
                continue
            prefix = f"{surface_prefix}{field_name}"
            if row_surface and field_name in {"score", "probability", "probability_by_class"}:
                prefix = f"{surface_prefix}{row_surface}.{field_name}"
            _collect_numeric(
                out,
                prefix=prefix,
                value=value,
                track=str(track),
                group=str(group),
                length=length,
                skip_fields=skip_fields,
            )
    return out


def _assistant_turn_key(row: Mapping[str, Any]) -> tuple[str, int] | None:
    """``seed_x__sol__assistant_003`` -> (``seed_x__sol``, 3)."""

    example_key = str(row.get("example_key") or row.get("example_id") or "")
    trace_id, sep, assistant_index = example_key.rpartition("__assistant_")
    if not sep or not assistant_index.isdigit():
        return None
    return trace_id, int(assistant_index)


def _track_group_from_row(row: Mapping[str, Any], labels: Mapping[str, Any]) -> tuple[Any, Any]:
    track = labels.get("track")
    group = labels.get("paired_group_id")
    example_key = str(row.get("example_key") or row.get("example_id") or "")
    if "__" not in example_key:
        return track, group
    trace_id, sep, assistant_index = example_key.rpartition("__assistant_")
    if not sep:
        trace_id = example_key
        assistant_index = ""
    parts = trace_id.rsplit("__", 1)
    if len(parts) != 2:
        return track, group
    parsed_group, parsed_track = parts
    resolved_group = group or parsed_group
    if assistant_index:
        resolved_group = f"{resolved_group}__assistant_{assistant_index}"
    return track or parsed_track, resolved_group


def _row_surface(row: Mapping[str, Any]) -> str | None:
    for key in ("coordinate", "emotion", "probe"):
        value = row.get(key)
        if value:
            return str(value)
    return None


def _collect_numeric(
    out: list[dict[str, Any]],
    *,
    prefix: str,
    value: Any,
    track: str,
    group: str,
    length: Any,
    skip_fields: set[str],
) -> None:
    leaf = prefix.rsplit(".", 1)[-1]
    if leaf in skip_fields:
        return
    if isinstance(value, bool):
        return
    if isinstance(value, (int, float)):
        out.append(
            {
                "surface": prefix,
                "value": float(value),
                "track": track,
                "group": group,
                "length": float(length) if isinstance(length, (int, float)) else None,
            }
        )
    elif isinstance(value, Mapping):
        for key, nested in value.items():
            _collect_numeric(
                out,
                prefix=f"{prefix}.{key}",
                value=nested,
                track=track,
                group=group,
                length=length,
                skip_fields=skip_fields,
            )


def merge_rows(*row_groups: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    for group in row_groups:
        merged.extend(dict(row) for row in group)
    return merged
