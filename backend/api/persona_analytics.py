"""Persona-vector math and cohort analytics.

Aggregates activation scores into persona vectors (see
backend.api.persona_vectors), computes cohort/track comparisons (eta-squared,
paired Cohen's d), workflow/action deltas, and outlier surfaces for the
product-analytics and persona-overview payloads.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from functools import lru_cache
from typing import Any

from backend.api.models import AuditTrace
from backend.api.persona_vectors import (
    EMOTION_CLUSTER_VECTORS,
    LEGACY_EMOTION_CLUSTER_VECTORS,
    OVERVIEW_EMOTION_CLUSTER_VECTORS,
    OVERVIEW_PERSONA_VECTORS,
    PERSONA_VECTOR_NAMES,
    PERSONA_VECTORS,
    VECTOR_DIRECTIONS,
)
from backend.api.registry import get_provider, provider_descriptor, resolve_provider
from backend.api.scores import (
    emotion_cluster_metadata_by_coordinate,
    score_rows_for_coordinates,
    score_surface,
)
from backend.api.stats import as_float as _as_float
from backend.api.stats import cohen_d as _cohen_d
from backend.api.stats import mean as _mean
from backend.api.stats import quantile as _quantile
from backend.api.stats import rms as _rms
from backend.api.stats import stddev as _stddev
from backend.api.trace_source import TRACK_PREFERRED_ORDER


def persona_overview(traces: Sequence[AuditTrace], provider: str | None = None) -> dict[str, Any]:
    provider_id = resolve_provider(provider)
    descriptor = provider_descriptor(provider_id)
    records = _persona_records(traces, provider=provider_id)
    surface = score_surface(provider=provider_id)
    if not records:
        if surface.get("available"):
            return _aggregate_persona_overview(surface, descriptor)
        return {"available": False}
    outliers = _workflow_outliers(records)[:40]
    features = descriptor.get("features") if isinstance(descriptor.get("features"), Mapping) else {}
    track_comparison = _track_comparison(records) if features.get("show_track_comparison") else {"available": False}
    workflow_action_rows = _workflow_action_matrix(records)
    low_n_task_action_count = sum(1 for row in workflow_action_rows if int(row.get("n") or 0) < 10)
    return {
        "available": True,
        "frame": {
            "thesis": "Persona and emotion activations provide a first-layer behavioral surface over product interactions.",
            "constraint": "These reads are directional triage signals, not reward predictors. Session-level interpretation lives in the session drilldown.",
            "dataset_note": descriptor["dataset_label"],
        },
        "reward_math": _reward_math(records, provider=provider_id),
        "vector_inventory": _vector_inventory(records, surface),
        "persona_vectors": list(OVERVIEW_PERSONA_VECTORS),
        "emotion_cluster_vectors": list(OVERVIEW_EMOTION_CLUSTER_VECTORS),
        "legacy_emotion_vectors": list(LEGACY_EMOTION_CLUSTER_VECTORS),
        "normalization_note": "Segment z-deltas use frozen per-run global mean/sd over raw direction-oriented values. Min-max normalized values are presentation-only.",
        "track_comparison": track_comparison,
        "workflow_vector_deltas": _group_vector_deltas(records, "workflow"),
        "top_workflow_deltas": _top_group_deltas(records, "workflow"),
        "action_vector_deltas": _group_vector_deltas(records, "final_action"),
        "top_action_deltas": _top_group_deltas(records, "final_action"),
        "simulated_trace_series": _simulated_trace_series(records),
        "hero_cancel_refund": _cancel_refund_paths(records),
        "workflow_action_matrix": workflow_action_rows,
        "low_n_task_action_count": low_n_task_action_count,
        "turn_count_quartiles": _turn_count_quartiles(records),
        "workflow_outcome_deltas": _workflow_outcome_deltas(records)[:8],
        "outliers": outliers,
        "outlier_turn_series": _outlier_turn_series(records, outliers, provider=provider_id),
        "task_instability": _task_instability(records)[:10],
        "methodology_notes": [
            f"{descriptor['segment_label']} labels come from the active provider normalization layer.",
            f"{descriptor['action_label']} labels come from the active provider normalization layer.",
            "Displayed z-deltas are computed from raw direction-oriented projections against the current run's global basis.",
            "Min-max normalized trait-intensity scores are used only for compact visual fills and the example storyboard.",
            "The deployment preview storyboard uses synthetic task-mode segments, not real deployment time.",
            "Outlier score is root-mean-square z-score across selected persona and emotion-cluster vectors within the trace workflow.",
            "Outlier turn charts compare each assistant turn with traces in a similar length bucket and relative turn-position bucket.",
            "High-stakes probes stay on the Overview page; product analytics focuses on persona, emotion, workflow, and action baselines.",
        ],
    }


def _vector_values(records: Sequence[Mapping[str, Any]], vector: str) -> list[float]:
    return [value for value in (_basis_value(row, vector) for row in records) if value is not None]


def _vector_stats(records: Sequence[Mapping[str, Any]], vector: str) -> dict[str, Any]:
    return compute_basis(records, (vector,)).get(vector, _empty_basis(vector))


def _percentile(sorted_or_unsorted_values: Sequence[float], value: float) -> float:
    values = sorted(sorted_or_unsorted_values)
    if not values:
        return 0.0
    below_or_equal = sum(1 for candidate in values if candidate <= value)
    return below_or_equal / len(values)


def _quintile_band(value: float, surface: Mapping[str, Any]) -> str | None:
    q20 = _as_float(surface.get("q20"))
    q40 = _as_float(surface.get("q40"))
    q60 = _as_float(surface.get("q60"))
    q80 = _as_float(surface.get("q80"))
    if None in (q20, q40, q60, q80):
        return None
    if value >= q80:
        return "A"
    if value >= q60:
        return "B"
    if value >= q40:
        return "C"
    if value >= q20:
        return "D"
    return "E"


def _round_or_none(value: Any) -> float | None:
    numeric = _as_float(value)
    return round(numeric, 6) if numeric is not None else None


def _workflow_label(task: Mapping[str, Any], provider: str | None) -> str:
    """Provider-specific task -> workflow taxonomy; generic sources get one bucket."""

    hook = get_provider(provider).workflow_from_task
    return hook(task) if hook else "Info/lookup"


def _persona_records(traces: Sequence[AuditTrace], provider: str | None = None) -> list[dict[str, Any]]:
    rows = score_rows_for_coordinates(_persona_coordinates(), provider=provider)
    if rows is None:
        return []
    trace_ids = {trace.trace_id for trace in traces}
    coordinates = set(_persona_coordinates())
    by_trace: dict[str, dict[str, list[float]]] = {trace_id: {} for trace_id in trace_ids}
    for row in rows:
        trace_id = str(row.get("trace_id") or "")
        coordinate = str(row.get("coordinate") or "")
        score = row.get("score")
        score_family = str(row.get("score_family") or "")
        if score_family and score_family not in {"assistant_axis", "emotion"}:
            continue
        if trace_id not in trace_ids or coordinate not in coordinates or score is None:
            continue
        by_trace.setdefault(trace_id, {}).setdefault(coordinate, []).append(float(score))

    records: list[dict[str, Any]] = []
    for trace in traces:
        values = by_trace.get(trace.trace_id, {})
        if not values:
            continue
        metadata = dict(trace.metadata)
        task = metadata.get("task") if isinstance(metadata.get("task"), Mapping) else {}
        reward_breakdown = (
            metadata.get("reward_breakdown") if isinstance(metadata.get("reward_breakdown"), Mapping) else {}
        )
        record: dict[str, Any] = {
            "trace_id": trace.trace_id,
            "task_id": trace.task_id,
            "workflow": str(metadata.get("workflow") or _workflow_label(task, provider)),
            "final_action": str(metadata.get("final_action") or "no final action"),
            "reward": float(trace.reward) if trace.reward is not None else None,
            "outcome": trace.outcome,
            "turn_count": len(trace.turns),
            "assistant_turn_count": sum(1 for turn in trace.turns if turn.role == "assistant" and turn.content),
            "user_chars": sum(len(turn.content or "") for turn in trace.turns if turn.role == "user"),
            "db_reward": _as_float(reward_breakdown.get("DB")),
            "communicate_reward": _as_float(reward_breakdown.get("COMMUNICATE")),
        }
        for vector in PERSONA_VECTOR_NAMES:
            record[vector] = _persona_vector_value(values, vector)
        records.append(record)
    return _normalize_persona_records(records)


def _persona_coordinates() -> tuple[str, ...]:
    coordinates = {coordinate for group in PERSONA_VECTORS.values() for coordinate in group}
    for cluster_names in EMOTION_CLUSTER_VECTORS.values():
        for cluster_name in cluster_names:
            coordinates.update(_emotion_cluster_member_coordinates(cluster_name))
    return tuple(sorted(coordinates))


def _persona_vector_value(values: Mapping[str, list[float]], vector: str) -> float | None:
    if vector in EMOTION_CLUSTER_VECTORS:
        cluster_values: list[float] = []
        for cluster_name in EMOTION_CLUSTER_VECTORS[vector]:
            member_values = [
                score
                for coordinate in _emotion_cluster_member_coordinates(cluster_name)
                for score in values.get(coordinate, [])
            ]
            cluster_value = _mean(member_values)
            if cluster_value is not None:
                cluster_values.append(cluster_value)
        return _mean(cluster_values)
    vector_values = [score for coordinate in PERSONA_VECTORS.get(vector, ()) for score in values.get(coordinate, [])]
    return _mean(vector_values)


def _persona_vector_source_coordinates(vector: str) -> tuple[str, ...]:
    if vector in EMOTION_CLUSTER_VECTORS:
        return tuple(
            coordinate
            for cluster_name in EMOTION_CLUSTER_VECTORS[vector]
            for coordinate in _emotion_cluster_coordinates(cluster_name)
        )
    return PERSONA_VECTORS.get(vector, ())


def _emotion_cluster_coordinates(cluster_name: str) -> tuple[str, ...]:
    metadata = _emotion_cluster_metadata_by_name().get(cluster_name)
    coordinate = metadata.get("coordinate") if isinstance(metadata, Mapping) else None
    return (str(coordinate),) if coordinate else ()


def _emotion_cluster_member_coordinates(cluster_name: str) -> tuple[str, ...]:
    metadata = _emotion_cluster_metadata_by_name().get(cluster_name)
    member_coordinates = metadata.get("member_coordinates") if isinstance(metadata, Mapping) else None
    if not isinstance(member_coordinates, Sequence) or isinstance(member_coordinates, (str, bytes)):
        return ()
    return tuple(str(coordinate) for coordinate in member_coordinates)


@lru_cache(maxsize=1)
def _emotion_cluster_metadata_by_name() -> dict[str, Mapping[str, Any]]:
    return {
        str(row.get("cluster")): row
        for row in emotion_cluster_metadata_by_coordinate().values()
        if isinstance(row, Mapping) and row.get("cluster")
    }


def _normalize_persona_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    bounds: dict[str, tuple[float, float]] = {}
    for vector in PERSONA_VECTOR_NAMES:
        direction = VECTOR_DIRECTIONS.get(vector, 1)
        oriented_values = [direction * float(record[vector]) for record in records if record.get(vector) is not None]
        bounds[vector] = (min(oriented_values), max(oriented_values)) if oriented_values else (0.0, 0.0)

    for record in records:
        for vector in PERSONA_VECTOR_NAMES:
            raw_value = record.get(vector)
            record[f"{vector}_raw"] = raw_value
            if raw_value is None:
                continue
            direction = VECTOR_DIRECTIONS.get(vector, 1)
            oriented_value = direction * float(raw_value)
            min_value, max_value = bounds[vector]
            record[f"{vector}_oriented"] = oriented_value
            record[vector] = 0.5 if max_value == min_value else (oriented_value - min_value) / (max_value - min_value)
    return records


def _overview_vectors() -> tuple[str, ...]:
    return OVERVIEW_PERSONA_VECTORS + OVERVIEW_EMOTION_CLUSTER_VECTORS


def _basis_value(record: Mapping[str, Any], vector: str) -> float | None:
    value = record.get(f"{vector}_oriented")
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def compute_basis(cohort_records: Sequence[Mapping[str, Any]], vectors: Sequence[str]) -> dict[str, dict[str, Any]]:
    basis: dict[str, dict[str, Any]] = {}
    for vector in vectors:
        values = [value for value in (_basis_value(record, vector) for record in cohort_records) if value is not None]
        if not values:
            basis[vector] = _empty_basis(vector)
            continue
        sorted_values = sorted(values)
        basis[vector] = {
            "vector": vector,
            "coordinate": _persona_vector_primary_coordinate(vector),
            "family": "emotion_cluster" if vector in EMOTION_CLUSTER_VECTORS else "persona",
            "source_coordinates": list(_persona_vector_source_coordinates(vector)),
            "n": len(values),
            "mean": round(_mean(values) or 0.0, 6),
            "sd": round(_stddev(values), 6),
            "p05": round(_quantile(sorted_values, 0.05), 6),
            "p50": round(_quantile(sorted_values, 0.5), 6),
            "p95": round(_quantile(sorted_values, 0.95), 6),
        }
    return basis


def _empty_basis(vector: str) -> dict[str, Any]:
    return {
        "vector": vector,
        "coordinate": _persona_vector_primary_coordinate(vector),
        "family": "emotion_cluster" if vector in EMOTION_CLUSTER_VECTORS else "persona",
        "source_coordinates": list(_persona_vector_source_coordinates(vector)),
        "n": 0,
        "mean": None,
        "sd": None,
        "p05": None,
        "p50": None,
        "p95": None,
    }


def _reward_math(records: Sequence[Mapping[str, Any]], provider: str | None = None) -> dict[str, Any]:
    if not get_provider(provider).supports_reward_math:
        return {
            "trace_count": len(records),
            "assistant_turn_count": sum(int(record.get("assistant_turn_count") or 0) for record in records),
            "pass_count": None,
            "fail_count": None,
            "pass_rate": None,
            "db_failure_count": None,
            "communication_failure_count": None,
            "overlap_failure_count": None,
            "failure_union_count": None,
        }
    failed = [record for record in records if float(record.get("reward") or 0.0) < 1.0]
    db_failed = {
        str(record["trace_id"])
        for record in records
        if record.get("db_reward") is not None and float(record.get("db_reward") or 0.0) < 1.0
    }
    communicate_failed = {
        str(record["trace_id"])
        for record in records
        if record.get("communicate_reward") is not None and float(record.get("communicate_reward") or 0.0) < 1.0
    }
    return {
        "trace_count": len(records),
        "assistant_turn_count": sum(int(record.get("assistant_turn_count") or 0) for record in records),
        "pass_count": sum(1 for record in records if float(record.get("reward") or 0.0) >= 1.0),
        "fail_count": len(failed),
        "pass_rate": _mean([float(record.get("reward") or 0.0) for record in records]),
        "db_failure_count": len(db_failed),
        "communication_failure_count": len(communicate_failed),
        "overlap_failure_count": len(db_failed & communicate_failed),
        "failure_union_count": len(db_failed | communicate_failed),
    }


def _vector_inventory(
    records: Sequence[Mapping[str, Any]], surface: Mapping[str, Any] | None = None
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for vector in PERSONA_VECTOR_NAMES:
        coordinates = _persona_vector_source_coordinates(vector)
        values = [float(record[vector]) for record in records if record.get(vector) is not None]
        raw_values = [float(record[f"{vector}_raw"]) for record in records if record.get(f"{vector}_raw") is not None]
        oriented_values = [
            float(record[f"{vector}_oriented"]) for record in records if record.get(f"{vector}_oriented") is not None
        ]
        if not values:
            continue
        sorted_values = sorted(values)
        sorted_oriented = sorted(oriented_values)
        rows.append(
            {
                "vector": vector,
                "coordinates": list(coordinates),
                "source": "paper_emotion_cluster" if vector in EMOTION_CLUSTER_VECTORS else "coordinate",
                "source_clusters": list(EMOTION_CLUSTER_VECTORS.get(vector, ())),
                "family": "emotion_cluster" if vector in EMOTION_CLUSTER_VECTORS else "persona",
                "overview": vector in _overview_vectors(),
                "n": len(values),
                "mean": round(_mean(values) or 0.0, 6),
                "sd": round(_stddev(values), 6),
                "p05": round(_quantile(sorted_values, 0.05), 6),
                "p50": round(_quantile(sorted_values, 0.5), 6),
                "p95": round(_quantile(sorted_values, 0.95), 6),
                "raw_mean": round(_mean(raw_values) or 0.0, 6) if raw_values else None,
                "basis_mean": round(_mean(oriented_values) or 0.0, 6) if oriented_values else None,
                "basis_sd": round(_stddev(oriented_values), 6) if oriented_values else None,
                "basis_p05": round(_quantile(sorted_oriented, 0.05), 6) if oriented_values else None,
                "basis_p50": round(_quantile(sorted_oriented, 0.5), 6) if oriented_values else None,
                "basis_p95": round(_quantile(sorted_oriented, 0.95), 6) if oriented_values else None,
                "direction": VECTOR_DIRECTIONS.get(vector, 1),
                "display_scale": "minmax_trait_intensity",
                "delta_scale": "raw_oriented_z",
            }
        )
    existing = {str(row.get("vector")) for row in rows}
    if surface:
        rows.extend(_aggregate_emotion_cluster_inventory(surface, existing))
    return rows


def _aggregate_persona_overview(surface: Mapping[str, Any], descriptor: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "available": True,
        "frame": {
            "thesis": "Persona and emotion activations provide a first-layer behavioral surface over product interactions.",
            "constraint": "Offline mode is using bundled aggregate score-surface data; session-level raw persona rows are unavailable.",
            "dataset_note": descriptor["dataset_label"],
        },
        "reward_math": {"trace_count": 1},
        "vector_inventory": _aggregate_emotion_cluster_inventory(surface, set()),
        "persona_vectors": list(OVERVIEW_PERSONA_VECTORS),
        "emotion_cluster_vectors": list(OVERVIEW_EMOTION_CLUSTER_VECTORS),
        "legacy_emotion_vectors": list(LEGACY_EMOTION_CLUSTER_VECTORS),
        "normalization_note": "Offline aggregate mode uses bundled score-surface summaries.",
        "workflow_vector_deltas": [],
        "top_workflow_deltas": [],
        "action_vector_deltas": [],
        "top_action_deltas": [],
        "simulated_trace_series": [],
        "hero_cancel_refund": [],
        "workflow_action_matrix": [],
        "low_n_task_action_count": 0,
        "turn_count_quartiles": {},
        "workflow_outcome_deltas": [],
        "outliers": [],
        "outlier_turn_series": {},
        "task_instability": [],
        "methodology_notes": [
            "Offline aggregate mode is backed by bundled score-surface JSON rather than live Neon score rows.",
        ],
    }


def _aggregate_emotion_cluster_inventory(surface: Mapping[str, Any], existing: set[str]) -> list[dict[str, Any]]:
    by_cluster = {
        str(row.get("cluster")): row for row in surface.get("emotion_clusters", []) if isinstance(row, Mapping)
    }
    rows: list[dict[str, Any]] = []
    for vector, clusters in EMOTION_CLUSTER_VECTORS.items():
        if vector in existing:
            continue
        cluster_rows = [by_cluster[cluster] for cluster in clusters if cluster in by_cluster]
        if not cluster_rows:
            continue
        means = [_as_float(row.get("mean")) for row in cluster_rows]
        means = [value for value in means if value is not None]
        aggregate_mean = round(_mean(means) or 0.0, 6) if means else None
        rows.append(
            {
                "vector": vector,
                "coordinates": [str(row.get("coordinate")) for row in cluster_rows if row.get("coordinate")],
                "source": "paper_emotion_cluster",
                "source_clusters": list(clusters),
                "family": "emotion_cluster",
                "overview": vector in _overview_vectors(),
                "n": sum(int(row.get("rows") or 0) for row in cluster_rows),
                "mean": aggregate_mean,
                "sd": None,
                "p05": None,
                "p50": None,
                "p95": None,
                "raw_mean": aggregate_mean,
                "basis_mean": aggregate_mean,
                "basis_sd": None,
                "basis_p05": None,
                "basis_p50": None,
                "basis_p95": None,
                "direction": VECTOR_DIRECTIONS.get(vector, 1),
                "display_scale": "aggregate_score_surface",
                "delta_scale": "aggregate_score_surface",
            }
        )
    return rows


def _cancel_refund_paths(records: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    grouped = _group_by((record for record in records if record.get("workflow") == "Cancel/refund"), "final_action")
    rows = [
        group_summary(action, group, label_key="final_action", vectors=PERSONA_VECTOR_NAMES)
        for action, group in grouped.items()
    ]
    rows.sort(key=lambda row: (row["pass_rate"], -row["n"]))
    return rows


def _group_vector_deltas(records: Sequence[Mapping[str, Any]], group_key: str, min_n: int = 7) -> list[dict[str, Any]]:
    global_basis = compute_basis(records, PERSONA_VECTOR_NAMES)

    rows: list[dict[str, Any]] = []
    for group_name, group in _group_by(records, group_key).items():
        if len(group) < min_n:
            continue
        rewards = [float(record.get("reward") or 0.0) for record in group]
        for vector in PERSONA_VECTOR_NAMES:
            values = [_basis_value(record, vector) for record in group]
            values = [value for value in values if value is not None]
            display_values = [float(record[vector]) for record in group if record.get(vector) is not None]
            raw_values = [float(record[f"{vector}_raw"]) for record in group if record.get(f"{vector}_raw") is not None]
            if not values:
                continue
            global_stats = global_basis.get(vector, _empty_basis(vector))
            global_mean = _as_float(global_stats.get("mean")) or 0.0
            global_sd = _as_float(global_stats.get("sd")) or 0.0
            mean_value = _mean(values) or 0.0
            delta = mean_value - global_mean
            rows.append(
                {
                    "group": group_name,
                    "group_key": group_key,
                    "vector": vector,
                    "n": len(values),
                    "pass_rate": round(_mean(rewards) or 0.0, 6),
                    "mean": round(mean_value, 6),
                    "global_mean": round(global_mean, 6),
                    "delta": round(delta, 6),
                    "standardized_delta": round(delta / global_sd, 6) if global_sd else None,
                    "display_mean": round(_mean(display_values) or 0.0, 6) if display_values else None,
                    "raw_mean": round(_mean(raw_values) or 0.0, 6) if raw_values else None,
                    "family": "emotion_cluster" if vector in EMOTION_CLUSTER_VECTORS else "persona",
                    "delta_scale": "raw_oriented_z",
                }
            )
    rows.sort(key=lambda row: abs(float(row["standardized_delta"] or row["delta"])), reverse=True)
    return rows


def _track_comparison(
    records: Sequence[Mapping[str, Any]],
    *,
    group_key: str = "final_action",
    control_group: str = "control",
    preferred_order: Sequence[str] = TRACK_PREFERRED_ORDER,
) -> dict[str, Any]:
    """Direct compare/contrast between persona tracks.

    Unlike _group_vector_deltas, nothing here is measured against the pooled
    all-track basis: per-track summaries stand alone, contrasts are
    between-track with the control track as the reference, and the seed
    pairing (the same task_id answered once per track) backs paired per-seed
    deltas and win counts. The pooled basis is the wrong reference for the
    demo because its SD includes between-track variance, so the standardized
    deltas shrink exactly when the tracks separate.
    """

    groups = _group_by(records, group_key)
    if control_group not in groups or len(groups) < 2:
        return {"available": False}
    tracks = [name for name in preferred_order if name in groups]
    tracks.extend(name for name in sorted(groups) if name not in tracks)
    non_control = [track for track in tracks if track != control_group]
    contrast_pairs = [(track, control_group) for track in non_control]
    contrast_pairs.extend(
        (first, second) for index, first in enumerate(non_control) for second in non_control[index + 1 :]
    )

    paired_seeds = set.intersection(
        *({str(record.get("task_id") or "") for record in groups[track]} for track in tracks)
    )

    vector_rows: list[dict[str, Any]] = []
    for vector in PERSONA_VECTOR_NAMES:
        basis_by_track = {
            track: [value for value in (_basis_value(record, vector) for record in groups[track]) if value is not None]
            for track in tracks
        }
        if not any(basis_by_track.values()):
            continue
        display_by_track = {
            track: [float(record[vector]) for record in groups[track] if record.get(vector) is not None]
            for track in tracks
        }
        seeds_by_track = {track: _seed_vector_values(groups[track], vector) for track in tracks}

        track_summaries = []
        for track in tracks:
            basis_values = basis_by_track[track]
            display_values = display_by_track[track]
            if not basis_values:
                continue
            track_summaries.append(
                {
                    "track": track,
                    "n": len(basis_values),
                    "basis_mean": round(_mean(basis_values) or 0.0, 6),
                    "basis_sd": round(_stddev(basis_values), 6),
                    "display_mean": round(_mean(display_values) or 0.0, 6) if display_values else None,
                    "display_se": (
                        round(_stddev(display_values) / len(display_values) ** 0.5, 6)
                        if len(display_values) > 1
                        else None
                    ),
                }
            )

        contrasts = []
        for first, second in contrast_pairs:
            shared_seeds = sorted(set(seeds_by_track[first]) & set(seeds_by_track[second]))
            deltas = []
            display_deltas = []
            for seed in shared_seeds:
                first_values = seeds_by_track[first][seed]
                second_values = seeds_by_track[second][seed]
                deltas.append(first_values["basis"] - second_values["basis"])
                if first_values["display"] is not None and second_values["display"] is not None:
                    display_deltas.append(first_values["display"] - second_values["display"])
            if not deltas:
                continue
            mean_delta = _mean(deltas) or 0.0
            delta_sd = _stddev(deltas)
            unpaired_d = _cohen_d(basis_by_track[first], basis_by_track[second])
            contrasts.append(
                {
                    "a": first,
                    "b": second,
                    "n_pairs": len(deltas),
                    "mean_delta": round(mean_delta, 6),
                    "display_mean_delta": round(_mean(display_deltas) or 0.0, 6) if display_deltas else None,
                    "paired_d": round(mean_delta / delta_sd, 6) if delta_sd else None,
                    "cohen_d": round(unpaired_d, 6) if unpaired_d is not None else None,
                    "wins": sum(1 for delta in deltas if delta > 0),
                    "losses": sum(1 for delta in deltas if delta < 0),
                    "ties": sum(1 for delta in deltas if delta == 0),
                }
            )

        separation = _eta_squared(basis_by_track)
        vector_rows.append(
            {
                "vector": vector,
                "family": "emotion_cluster" if vector in EMOTION_CLUSTER_VECTORS else "persona",
                "overview": vector in _overview_vectors(),
                "eta_squared": round(separation, 6) if separation is not None else None,
                "tracks": track_summaries,
                "contrasts": contrasts,
            }
        )

    vector_rows.sort(key=lambda row: float(row["eta_squared"] or 0.0), reverse=True)
    return {
        "available": True,
        "group_key": group_key,
        "control": control_group,
        "tracks": [{"track": track, "n": len(groups[track])} for track in tracks],
        "paired_task_count": len(paired_seeds),
        "vectors": vector_rows,
        "notes": [
            "Per-track means and contrasts are computed directly between tracks, never against the pooled all-track baseline.",
            "Paired contrasts use seeds answered by both tracks (same task_id); wins count seeds where the first track's direction-oriented score is higher.",
            "Separation (eta squared) is the share of direction-oriented score variance explained by track membership.",
        ],
    }


def _seed_vector_values(group: Sequence[Mapping[str, Any]], vector: str) -> dict[str, dict[str, float | None]]:
    by_seed: dict[str, dict[str, list[float]]] = {}
    for record in group:
        basis = _basis_value(record, vector)
        if basis is None:
            continue
        seed = str(record.get("task_id") or record.get("trace_id") or "")
        bucket = by_seed.setdefault(seed, {"basis": [], "display": []})
        bucket["basis"].append(basis)
        display = record.get(vector)
        if display is not None:
            bucket["display"].append(float(display))
    return {
        seed: {
            "basis": _mean(values["basis"]) or 0.0,
            "display": _mean(values["display"]) if values["display"] else None,
        }
        for seed, values in by_seed.items()
    }


def _eta_squared(values_by_group: Mapping[str, Sequence[float]]) -> float | None:
    all_values = [value for values in values_by_group.values() for value in values]
    if len(all_values) < 3:
        return None
    grand_mean = _mean(all_values) or 0.0
    ss_total = sum((value - grand_mean) ** 2 for value in all_values)
    if ss_total == 0:
        return 0.0
    ss_between = sum(
        len(values) * ((_mean(list(values)) or 0.0) - grand_mean) ** 2 for values in values_by_group.values() if values
    )
    return ss_between / ss_total


def _top_group_deltas(records: Sequence[Mapping[str, Any]], group_key: str, min_n: int = 7) -> list[dict[str, Any]]:
    top_by_group: dict[str, dict[str, Any]] = {}
    for row in _group_vector_deltas(records, group_key, min_n=min_n):
        group = str(row["group"])
        current = top_by_group.get(group)
        if current is None or abs(float(row["standardized_delta"] or row["delta"])) > abs(
            float(current["standardized_delta"] or current["delta"])
        ):
            top_by_group[group] = dict(row)
    rows = list(top_by_group.values())
    rows.sort(key=lambda row: abs(float(row["standardized_delta"] or row["delta"])), reverse=True)
    return rows


def _workflow_action_matrix(records: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[Mapping[str, Any]]] = {}
    for record in records:
        key = (str(record.get("workflow")), str(record.get("final_action")))
        grouped.setdefault(key, []).append(record)
    rows: list[dict[str, Any]] = []
    for (workflow, action), group in grouped.items():
        summary = group_summary(action, group, label_key="final_action", vectors=PERSONA_VECTOR_NAMES)
        summary["workflow"] = workflow
        rows.append(summary)
    rows.sort(key=lambda row: (row["workflow"], -row["n"], row["final_action"]))
    return rows


def _turn_count_quartiles(records: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    ordered = sorted(records, key=lambda record: int(record.get("turn_count") or 0))
    rows: list[dict[str, Any]] = []
    if not ordered:
        return rows
    for index in range(4):
        start = index * len(ordered) // 4
        end = (index + 1) * len(ordered) // 4
        group = ordered[start:end]
        if not group:
            continue
        row = group_summary(f"Q{index + 1}", group, label_key="final_action", vectors=PERSONA_VECTOR_NAMES)
        row["quartile"] = f"Q{index + 1}"
        row["turn_count_min"] = min(int(record.get("turn_count") or 0) for record in group)
        row["turn_count_max"] = max(int(record.get("turn_count") or 0) for record in group)
        row["turn_count_mean"] = round(_mean([float(record.get("turn_count") or 0) for record in group]) or 0.0, 4)
        rows.append(row)
    return rows


def _simulated_trace_series(records: Sequence[Mapping[str, Any]], window_size: int = 20) -> dict[str, Any]:
    vectors = (
        "assistant_axis",
        "sycophantic",
        "assertive",
        "decisive",
        "cautious",
        "conciliatory",
        "fear_and_overwhelm",
        "compassionate_gratitude",
    )
    mode_sequence = (
        "Book flight",
        "Cancel/refund",
        "Flight change/cabin",
        "Compensation",
        "Info/lookup",
        "Book flight",
        "Cancel/refund",
        "Flight change/cabin",
        "Insurance",
        "Baggage/passenger",
    )
    by_workflow = _group_by(records, "workflow")
    offsets: dict[str, int] = {}
    rows: list[dict[str, Any]] = []
    for index, mode in enumerate(mode_sequence):
        group = sorted(by_workflow.get(mode, []), key=lambda record: str(record.get("trace_id")))
        if not group:
            continue
        offset = offsets.get(mode, 0)
        window = [group[(offset + step) % len(group)] for step in range(min(window_size, len(group)))]
        offsets[mode] = offset + window_size
        start = index * window_size
        row: dict[str, Any] = {
            "bucket": index + 1,
            "label": f"{start + 1}-{start + window_size}",
            "mode": mode,
            "n": len(window),
            "source_n": len(group),
            "trace_index_start": start + 1,
            "trace_index_end": start + window_size,
            "pass_rate": round(_mean([float(record.get("reward") or 0.0) for record in window]) or 0.0, 6),
        }
        for vector in vectors:
            values = [float(record[vector]) for record in window if record.get(vector) is not None]
            row[vector] = round(_mean(values) or 0.0, 6) if values else None
        rows.append(row)
    return {
        "available": bool(rows),
        "frame": "Example-only deployment preview storyboard. Each 20-session block is sorted from Tau2 task labels; block boundaries are sorting artifacts, not observed drift.",
        "window_size": window_size,
        "vectors": list(vectors),
        "rows": rows,
    }


def _outlier_turn_series(
    records: Sequence[Mapping[str, Any]], outliers: Sequence[Mapping[str, Any]], provider: str | None = None
) -> list[dict[str, Any]]:
    outlier_ids = {str(row.get("trace_id")) for row in outliers}
    if not outlier_ids:
        return []
    turn_records = _persona_turn_records(records, provider=provider)
    if not turn_records:
        return []
    selected = _overview_vectors()
    length_values = sorted({int(record.get("turn_count") or 0) for record in records})
    length_thresholds = [_quantile(length_values, q) for q in (0.25, 0.5, 0.75)] if length_values else [0.0, 0.0, 0.0]

    bucketed_turns: dict[tuple[int, int], list[Mapping[str, Any]]] = {}
    for record in turn_records:
        bucketed_turns.setdefault(_turn_baseline_key(record, length_thresholds), []).append(record)

    baseline_stats: dict[tuple[int, int], dict[str, dict[str, Any]]] = {}
    for key, bucket_records in bucketed_turns.items():
        baseline_stats[key] = compute_basis(bucket_records, selected)

    scored_turns: list[dict[str, Any]] = []
    for record in turn_records:
        key = _turn_baseline_key(record, length_thresholds)
        z_scores: dict[str, float] = {}
        z2_sum = 0.0
        used = 0
        for vector in selected:
            value = _basis_value(record, vector)
            stats = baseline_stats.get(key, {}).get(vector, {})
            mean_value = _as_float(stats.get("mean")) or 0.0
            sd_value = _as_float(stats.get("sd")) or 0.0
            if value is None or sd_value == 0:
                continue
            z = (value - mean_value) / sd_value
            z_scores[vector] = z
            z2_sum += z * z
            used += 1
        if not used:
            continue
        top_z = _top_z_items(z_scores, limit=3)
        scored_turns.append(
            {
                **record,
                "baseline_key": key,
                "outlier_score": (z2_sum / used) ** 0.5,
                "z_scores": z_scores,
                "top_z": top_z,
            }
        )

    baseline_by_key: dict[tuple[int, int], float] = {}
    for key, group in _group_by_key(scored_turns, "baseline_key").items():
        baseline_by_key[key] = _mean([float(row["outlier_score"]) for row in group]) or 0.0

    outlier_meta = {str(row.get("trace_id")): row for row in outliers}
    series: list[dict[str, Any]] = []
    for trace_id in outlier_ids:
        trace_rows = [row for row in scored_turns if str(row.get("trace_id")) == trace_id]
        if not trace_rows:
            continue
        trace_rows.sort(key=lambda row: int(row.get("turn_index") or 0))
        meta = outlier_meta.get(trace_id, {})
        tracked_vector = str(meta.get("selected_vector") or _tracked_outlier_vector(trace_rows))
        tracked_meta = next(
            (row for row in meta.get("top_z", []) if row.get("vector") == tracked_vector),
            {
                "vector": tracked_vector,
                "coordinate": _persona_vector_primary_coordinate(tracked_vector),
                "z": 0.0,
                "polarity": "high",
            },
        )
        series.append(
            {
                "trace_id": trace_id,
                "workflow": meta.get("workflow") or trace_rows[0].get("workflow"),
                "final_action": meta.get("final_action") or trace_rows[0].get("final_action"),
                "reward": meta.get("reward"),
                "trace_outlier_score": meta.get("outlier_score"),
                "tracked_vector": tracked_vector,
                "tracked_coordinate": tracked_meta.get("coordinate"),
                "tracked_polarity": tracked_meta.get("polarity"),
                "tracked_trace_z": tracked_meta.get("z"),
                "turn_count": trace_rows[0].get("turn_count"),
                "baseline_frame": "Dotted baseline is zero signed z for traces in the same conversation-length quartile and relative turn-position bucket.",
                "rows": [
                    {
                        "turn_index": int(row.get("turn_index") or 0),
                        "relative_position": round(float(row.get("relative_position") or 0.0), 4),
                        "outlier_score": round(float(row["outlier_score"]), 6),
                        "length_baseline": round(baseline_by_key.get(row["baseline_key"], 0.0), 6),
                        "tracked_z": round(float(row.get("z_scores", {}).get(tracked_vector, 0.0)), 6),
                        "top_deviation": row["top_z"][0] if row.get("top_z") else None,
                    }
                    for row in trace_rows
                ],
            }
        )
    series.sort(key=lambda row: float(row.get("trace_outlier_score") or 0.0), reverse=True)
    return series


def _tracked_outlier_vector(trace_rows: Sequence[Mapping[str, Any]]) -> str:
    totals: dict[str, float] = {}
    for row in trace_rows:
        for vector, z in row.get("z_scores", {}).items():
            totals[vector] = totals.get(vector, 0.0) + abs(float(z))
    if not totals:
        return "assistant_axis"
    return max(totals.items(), key=lambda item: item[1])[0]


def _persona_turn_records(records: Sequence[Mapping[str, Any]], provider: str | None = None) -> list[dict[str, Any]]:
    rows = score_rows_for_coordinates(_persona_coordinates(), provider=provider)
    if rows is None:
        return []
    metadata = {str(record.get("trace_id")): record for record in records}
    coordinates = set(_persona_coordinates())
    by_turn: dict[tuple[str, int], dict[str, list[float]]] = {}
    for row in rows:
        trace_id = str(row.get("trace_id") or "")
        turn_index = row.get("turn_index")
        coordinate = str(row.get("coordinate") or "")
        score = row.get("score")
        score_family = str(row.get("score_family") or "")
        if score_family and score_family not in {"assistant_axis", "emotion"}:
            continue
        if trace_id not in metadata or turn_index is None or coordinate not in coordinates or score is None:
            continue
        by_turn.setdefault((trace_id, int(turn_index)), {}).setdefault(coordinate, []).append(float(score))

    turn_records: list[dict[str, Any]] = []
    for (trace_id, turn_index), values in by_turn.items():
        meta = metadata[trace_id]
        turn_count = int(meta.get("turn_count") or 0)
        record: dict[str, Any] = {
            "trace_id": trace_id,
            "turn_index": turn_index,
            "workflow": meta.get("workflow"),
            "final_action": meta.get("final_action"),
            "reward": meta.get("reward"),
            "turn_count": turn_count,
            "relative_position": turn_index / max(turn_count - 1, 1),
        }
        for vector in PERSONA_VECTOR_NAMES:
            record[vector] = _persona_vector_value(values, vector)
        turn_records.append(record)
    return _normalize_persona_records(turn_records)


def _turn_baseline_key(record: Mapping[str, Any], length_thresholds: Sequence[float]) -> tuple[int, int]:
    turn_count = int(record.get("turn_count") or 0)
    length_bucket = 1 + sum(1 for threshold in length_thresholds if turn_count > threshold)
    relative_position = max(0.0, min(0.9999, float(record.get("relative_position") or 0.0)))
    position_bucket = int(relative_position * 5) + 1
    return length_bucket, position_bucket


def _group_by_key(records: Iterable[Mapping[str, Any]], key: str) -> dict[Any, list[Mapping[str, Any]]]:
    grouped: dict[Any, list[Mapping[str, Any]]] = {}
    for record in records:
        grouped.setdefault(record.get(key), []).append(record)
    return grouped


def _workflow_outcome_deltas(records: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for workflow, group in _group_by(records, "workflow").items():
        passed = [record for record in group if float(record.get("reward") or 0.0) >= 1.0]
        failed = [record for record in group if float(record.get("reward") or 0.0) < 1.0]
        if len(passed) < 4 or len(failed) < 4:
            continue
        for vector in PERSONA_VECTOR_NAMES:
            passed_values = [_basis_value(record, vector) for record in passed]
            failed_values = [_basis_value(record, vector) for record in failed]
            passed_values = [value for value in passed_values if value is not None]
            failed_values = [value for value in failed_values if value is not None]
            effect = _cohen_d(failed_values, passed_values)
            if effect is None:
                continue
            rows.append(
                {
                    "workflow": workflow,
                    "vector": vector,
                    "n_fail": len(failed_values),
                    "n_pass": len(passed_values),
                    "mean_fail": round(_mean(failed_values) or 0.0, 6),
                    "mean_pass": round(_mean(passed_values) or 0.0, 6),
                    "delta_fail_minus_pass": round((_mean(failed_values) or 0.0) - (_mean(passed_values) or 0.0), 6),
                    "cohen_d_fail_vs_pass": round(effect, 6),
                }
            )
    rows.sort(key=lambda row: abs(float(row["cohen_d_fail_vs_pass"])), reverse=True)
    return rows


def _workflow_outliers(records: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    selected = _overview_vectors()
    persona_set = set(OVERVIEW_PERSONA_VECTORS)
    emotion_set = set(OVERVIEW_EMOTION_CLUSTER_VECTORS)
    workflow_stats: dict[str, dict[str, dict[str, Any]]] = {}
    for workflow, group in _group_by(records, "workflow").items():
        workflow_stats[workflow] = compute_basis(group, selected)
    rows: list[dict[str, Any]] = []
    for record in records:
        z_scores: dict[str, float] = {}
        for vector in selected:
            value = _basis_value(record, vector)
            stats = workflow_stats.get(str(record.get("workflow")), {}).get(vector, {})
            mean_value = _as_float(stats.get("mean")) or 0.0
            sd_value = _as_float(stats.get("sd")) or 0.0
            if value is None or sd_value == 0:
                continue
            z = (value - mean_value) / sd_value
            z_scores[vector] = round(z, 4)
        family_groups = (
            ("persona", {vector: z for vector, z in z_scores.items() if vector in persona_set}),
            ("emotion_cluster", {vector: z for vector, z in z_scores.items() if vector in emotion_set}),
        )
        for family, family_scores in family_groups:
            aggregate = _rms(family_scores.values())
            if aggregate is None:
                continue
            top_z = _top_z_items(family_scores, limit=3)
            rows.append(
                {
                    "trace_id": record["trace_id"],
                    "workflow": record["workflow"],
                    "final_action": record["final_action"],
                    "reward": record["reward"],
                    "turn_count": record["turn_count"],
                    "baseline_scope": "workflow",
                    "baseline_label": _baseline_scope_label("workflow", record),
                    "baseline_n": int(
                        workflow_stats.get(str(record.get("workflow")), {}).get(top_z[0]["vector"], {}).get("n") or 0
                    )
                    if top_z
                    else 0,
                    "outlier_score": round(aggregate, 6),
                    "aggregate_kind": f"{family}_rms_z",
                    "top_z": top_z,
                    "selected_vector": top_z[0]["vector"] if top_z else None,
                    "family": family,
                    "vectors": {
                        vector: record.get(vector) for vector in (persona_set if family == "persona" else emotion_set)
                    },
                }
            )
    rows.sort(key=lambda row: float(row["outlier_score"]), reverse=True)
    return rows


def _top_z_items(z_scores: Mapping[str, float], limit: int = 3) -> list[dict[str, Any]]:
    rows = [
        {
            "vector": vector,
            "coordinate": _persona_vector_primary_coordinate(vector),
            "z": round(float(z), 4),
            "polarity": "low" if float(z) < 0 else "high",
        }
        for vector, z in z_scores.items()
    ]
    rows.sort(key=lambda row: abs(float(row["z"])), reverse=True)
    return rows[:limit]


def _persona_vector_primary_coordinate(vector: str) -> str | None:
    coordinates = _persona_vector_source_coordinates(vector)
    return coordinates[0] if coordinates else None


def _task_instability(records: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for task_id, group in _group_by(records, "task_id").items():
        rewards = [float(record.get("reward") or 0.0) for record in group]
        if len(group) < 2 or len(set(rewards)) < 2:
            continue
        posture_sds = []
        for vector in _overview_vectors():
            values = [_basis_value(record, vector) for record in group]
            values = [value for value in values if value is not None]
            if len(values) >= 2:
                posture_sds.append(_stddev(values))
        rows.append(
            {
                "task_id": task_id,
                "workflow": str(group[0].get("workflow")),
                "n": len(group),
                "pass_rate": round(_mean(rewards) or 0.0, 6),
                "rewards": rewards,
                "posture_sd": round(_mean(posture_sds) or 0.0, 6),
            }
        )
    rows.sort(key=lambda row: (float(row["posture_sd"]), len(row["rewards"])), reverse=True)
    return rows


def group_summary(
    label: str,
    group: Sequence[Mapping[str, Any]],
    *,
    label_key: str = "label",
    vectors: Sequence[str] = (),
) -> dict[str, Any]:
    """Reward summary for one group of records; optional per-vector means.

    Shared by the session product-group cards (label_key="label") and the
    persona final-action rows (label_key="final_action", vectors=persona set).
    """

    rewards = [float(record.get("reward") or 0.0) for record in group]
    row: dict[str, Any] = {
        label_key: label,
        "n": len(group),
        "pass_rate": round(_mean(rewards) or 0.0, 6) if rewards else None,
        "fail_count": sum(1 for reward in rewards if reward < 1.0),
    }
    for vector in vectors:
        values = [float(record[vector]) for record in group if record.get(vector) is not None]
        if values:
            row[vector] = round(_mean(values) or 0.0, 6)
    return row


def _group_by(records: Iterable[Mapping[str, Any]], key: str) -> dict[str, list[Mapping[str, Any]]]:
    grouped: dict[str, list[Mapping[str, Any]]] = {}
    for record in records:
        grouped.setdefault(str(record.get(key) or "unknown"), []).append(record)
    return grouped


def _preferred_session_scope(scope_rows: Mapping[str, Mapping[str, Any]], min_n: int = 10) -> tuple[str, str | None]:
    for scope in ("task_action", "workflow", "final_action"):
        n = int(scope_rows.get(scope, {}).get("n") or 0)
        if n >= min_n:
            if scope == "task_action":
                return scope, None
            return (
                scope,
                f"Task + action baseline hidden because n={int(scope_rows.get('task_action', {}).get('n') or 0)}.",
            )
    return "global", "Segment baselines below n=10; using global baseline."


def _baseline_scope_label(scope: str, record: Mapping[str, Any]) -> str:
    if scope in {"workflow", "task_group"}:
        return f"{record.get('workflow') or 'unknown'} workflow"
    if scope == "final_action":
        return f"{record.get('final_action') or 'no final action'} action"
    if scope == "task_action":
        return f"{record.get('workflow') or 'unknown'} / {record.get('final_action') or 'no final action'}"
    if scope == "repeated_task":
        return f"task {record.get('task_id') or 'unknown'}"
    return "global"
