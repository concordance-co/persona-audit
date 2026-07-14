"""Character-view computation for the System Portrait "Character" half.

Each persona trait is one point in two measurements of the same space:

    x = frequency        share of audited-provider traces where the trait is present
    y = distinctiveness  signed lift = audited present-rate - reference present-rate

Presence rule (v0): a trait is *present* in a trace when the maximum projection
score across the trace's turns exceeds a per-trait threshold (any turn crosses).
The threshold is the 80th percentile of the *reference* provider's per-trace-max
distribution for that trait, so the reference present-rate is ~0.20 by
construction. We always compute distinctiveness against the reference's
*measured* rate, never an assumed 0.20 -- ties and discretization mean it is not
exactly 0.20, and per-coordinate thresholds are what keep the comparison honest.

Distinctiveness is signed: a trait the audited model does *less* than the
reference (negative lift, suppressed) is real signal and is never clamped at 0.

The reference provider and audited provider are scored through the same projection vectors, so per-trait scores are comparable. A trait scored for the audited provider but missing from the reference cannot have a lift and is reported as dropped -- never silently omitted.

This module is the single source for Character numbers. The dashboard, the
future Monitor, and the future Report all read from here so they cannot disagree.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from typing import Any

from backend.api.assistant_traits import audit_assistant_traits
from backend.api.registry import resolve_provider
from backend.api.scores import score_rows_for_coordinates
from backend.api.stats import histogram_counts
from backend.api.trace_source import track_group_map

# tau2 is the cold-start reference distribution for distinctiveness. Better
# baseline data can be swapped in later by changing this provider id.
CHARACTER_REFERENCE_PROVIDER = "tau2"
# Track-comparison corpora (the persona demo) carry their own reference: the
# control track. Sol and Marrow are audited against it instead of tau2.
CHARACTER_CONTROL_TRACK = "control"
PERSONA_SCORE_FAMILY = "assistant_axis"
PERSONA_COORDINATE_PREFIX = "assistant_axis_trait__"
PRESENCE_QUANTILE = 0.80
# A reference distribution needs enough traces for its 80th percentile to mean
# something; below this we drop the trait rather than publish a noisy threshold.
MIN_REFERENCE_TRACES = 20
# Cap the drill-down payload; the full present-count is always reported.
TRAIT_DETAIL_TRACE_LIMIT = 250
# Bins for the per-trait distribution-shift histogram in the drill-down.
DISTRIBUTION_BINS = 22
# Segments for the within-conversation drift curve (start -> end).
DRIFT_SEGMENTS = 5
DRIFT_SEGMENT_LABELS = ("Start", "Early", "Middle", "Late", "End")
# v0 default "feared" traits driving the Tail view. Product-configurable later;
# selection is the same as Character (outliers in the projection), only which
# traits count as bad is product-specific.
CHARACTER_CONCERN_TRAITS = ("sycophantic", "manipulative", "hostile", "condescending")


def trait_name(coordinate: str) -> str:
    return str(coordinate or "").replace(PERSONA_COORDINATE_PREFIX, "")


def trait_label(coordinate: str) -> str:
    return trait_name(coordinate).replace("_", " ").strip().title()


def candidate_coordinates() -> tuple[str, ...]:
    """Union of both provider trait panels, as persona-trait coordinates."""

    traits: list[str] = []
    seen: set[str] = set()
    for trait in audit_assistant_traits():
        normalized = str(trait).strip().lower()
        if normalized and normalized not in seen:
            seen.add(normalized)
            traits.append(normalized)
    return tuple(f"{PERSONA_COORDINATE_PREFIX}{trait}" for trait in traits)


def _quantile(sorted_values: Sequence[float], q: float) -> float:
    """Linear-interpolated quantile over an already-sorted sequence."""

    n = len(sorted_values)
    if n == 0:
        return 0.0
    if n == 1:
        return float(sorted_values[0])
    position = q * (n - 1)
    low = int(position)
    high = min(low + 1, n - 1)
    frac = position - low
    return float(sorted_values[low]) * (1.0 - frac) + float(sorted_values[high]) * frac


def _per_trace_stats(rows: Sequence[Mapping[str, Any]]) -> dict[str, dict[str, dict[str, Any]]]:
    """Reduce raw score rows to per-coordinate, per-trace statistics.

    Returns ``coordinate -> trace_id -> {max, mean, peak_turn, turns}``. ``max``
    drives presence (any turn crosses); ``mean`` is the trace-level aggregate
    kept alongside for the later "spiked once vs. sustained" distinction.
    """

    acc: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for row in rows:
        coordinate = row.get("coordinate")
        trace_id = row.get("trace_id")
        score = row.get("score")
        if not coordinate or not trace_id or score is None:
            continue
        value = float(score)
        bucket = acc[coordinate].get(trace_id)
        if bucket is None:
            acc[coordinate][trace_id] = {
                "sum": value,
                "turns": 1,
                "max": value,
                "peak_turn": row.get("turn_index"),
            }
            continue
        bucket["sum"] += value
        bucket["turns"] += 1
        if value > bucket["max"]:
            bucket["max"] = value
            bucket["peak_turn"] = row.get("turn_index")

    out: dict[str, dict[str, dict[str, Any]]] = {}
    for coordinate, traces in acc.items():
        out[coordinate] = {
            trace_id: {
                "max": bucket["max"],
                "mean": bucket["sum"] / bucket["turns"],
                "peak_turn": bucket["peak_turn"],
                "turns": bucket["turns"],
            }
            for trace_id, bucket in traces.items()
        }
    return out


def _present_rate(trace_max: Sequence[float], threshold: float) -> tuple[int, int]:
    present = sum(1 for value in trace_max if value > threshold)
    return present, len(trace_max)


def _distribution_shift(
    audited_max: Sequence[float],
    reference_max: Sequence[float],
    threshold: float,
    *,
    n_bins: int = DISTRIBUTION_BINS,
) -> dict[str, Any]:
    """Shared-bin histogram of per-trace-max for audited vs reference.

    Bin heights are fractions of each provider's traces (densities), so the
    two distributions overlay despite different totals. The threshold line is
    where the tail begins -- the right edge of this view is the Tail half.
    """

    audited_total = len(audited_max)
    reference_total = len(reference_max)
    lo = min([*audited_max, *reference_max])
    hi = max([*audited_max, *reference_max])
    width = (hi - lo) / n_bins if hi > lo else 1.0

    audited_counts = histogram_counts(audited_max, lo, hi, n_bins)
    reference_counts = histogram_counts(reference_max, lo, hi, n_bins)
    bins = []
    for index in range(n_bins):
        x0 = lo + index * width
        bins.append(
            {
                "x0": round(x0, 4),
                "x1": round(x0 + width, 4),
                "mid": round(x0 + width / 2, 4),
                "audited": round(audited_counts[index] / audited_total, 5) if audited_total else 0.0,
                "reference": round(reference_counts[index] / reference_total, 5) if reference_total else 0.0,
            }
        )
    return {
        "bins": bins,
        "threshold": round(threshold, 6),
        "audited_total": audited_total,
        "reference_total": reference_total,
    }


def compute_character(
    reference_rows: Sequence[Mapping[str, Any]],
    audited_rows: Sequence[Mapping[str, Any]],
    *,
    quantile: float = PRESENCE_QUANTILE,
    min_reference_traces: int = MIN_REFERENCE_TRACES,
    audited_groups: Mapping[str, str] | None = None,
    group_order: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Pure computation: persona points + dropped traits from raw score rows.

    ``audited_groups`` (trace_id -> group, e.g. persona track) additionally
    splits each point's present-rate per group against the SAME reference
    threshold, so per-group frequency/distinctiveness stay comparable to the
    pooled point.
    """

    reference = _per_trace_stats(reference_rows)
    audited = _per_trace_stats(audited_rows)

    coordinates = sorted(set(reference) | set(audited))
    points: list[dict[str, Any]] = []
    dropped: list[dict[str, Any]] = []

    for coordinate in coordinates:
        if not coordinate.startswith(PERSONA_COORDINATE_PREFIX):
            continue
        audited_max = sorted(stat["max"] for stat in audited.get(coordinate, {}).values())
        reference_max = sorted(stat["max"] for stat in reference.get(coordinate, {}).values())

        if not audited_max:
            dropped.append(_dropped(coordinate, "no_audited", len(reference_max), 0))
            continue
        if len(reference_max) < min_reference_traces:
            dropped.append(_dropped(coordinate, "no_reference", len(reference_max), len(audited_max)))
            continue

        threshold = _quantile(reference_max, quantile)
        reference_present, reference_total = _present_rate(reference_max, threshold)
        audited_present, audited_total = _present_rate(audited_max, threshold)
        reference_rate = reference_present / reference_total
        audited_rate = audited_present / audited_total

        point = {
            "coordinate": coordinate,
            "trait": trait_name(coordinate),
            "label": trait_label(coordinate),
            "frequency": round(audited_rate, 4),
            "distinctiveness": round(audited_rate - reference_rate, 4),
            "reference_rate": round(reference_rate, 4),
            "threshold": round(threshold, 6),
            "audited_present": audited_present,
            "audited_total": audited_total,
            "reference_present": reference_present,
            "reference_total": reference_total,
        }
        if audited_groups:
            point["tracks"] = _group_score_means(
                audited.get(coordinate, {}),
                audited_groups,
                group_order or (),
            )
            reference_stats = reference.get(coordinate, {})
            point["reference_mean_score"] = _mean_of([stat["mean"] for stat in reference_stats.values()])
            point["reference_peak_mean"] = _mean_of([stat["max"] for stat in reference_stats.values()])
        points.append(point)

    points.sort(key=lambda point: point["distinctiveness"], reverse=True)
    return {
        "points": points,
        "dropped": dropped,
        "meta": {
            "score_family": PERSONA_SCORE_FAMILY,
            "presence_rule": "trace_max_gt_threshold",
            "threshold_basis": "reference_per_trace_max_quantile",
            "quantile": quantile,
            "trait_count": len(points),
            "dropped_count": len(dropped),
            "tracks": list(group_order or ()) if audited_groups else [],
        },
    }


def _mean_of(values: Sequence[float]) -> float | None:
    return round(sum(values) / len(values), 6) if values else None


def _group_score_means(
    trace_stats: Mapping[str, Mapping[str, Any]],
    groups: Mapping[str, str],
    group_order: Sequence[str],
) -> list[dict[str, Any]]:
    """Raw score magnitude per group: mean of per-trace mean and per-trace max.

    Deliberately not a present-rate or threshold-crossing count — the track
    comparison is about how strongly the trait reads per track, in the same
    raw score units everywhere.
    """

    by_group: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for trace_id, stat in trace_stats.items():
        by_group[groups.get(trace_id, "unknown")].append(stat)
    ordered = [group for group in group_order if group in by_group]
    ordered.extend(group for group in sorted(by_group) if group not in ordered)
    return [
        {
            "track": group,
            "mean_score": _mean_of([stat["mean"] for stat in by_group[group]]),
            "peak_mean": _mean_of([stat["max"] for stat in by_group[group]]),
            "traces": len(by_group[group]),
        }
        for group in ordered
    ]


def _dropped(coordinate: str, reason: str, reference_traces: int, audited_traces: int) -> dict[str, Any]:
    return {
        "coordinate": coordinate,
        "trait": trait_name(coordinate),
        "label": trait_label(coordinate),
        "reason": reason,
        "reference_traces": reference_traces,
        "audited_traces": audited_traces,
    }


def _segment_means(
    rows: Sequence[Mapping[str, Any]],
    n_segments: int,
) -> tuple[list[float | None], dict[str, Any]]:
    """Mean score per normalized conversation segment, plus per-session drift.

    Each conversation's scored turns are ordered and mapped onto [0, 1] by rank,
    so conversations of different lengths line up start-to-end. Single-turn
    conversations cannot drift and are excluded. The per-session summary compares
    each conversation's first third to its last third.
    """

    by_trace: dict[str, list[tuple[int, float]]] = defaultdict(list)
    for row in rows:
        score = row.get("score")
        trace_id = row.get("trace_id")
        if score is None or not trace_id:
            continue
        by_trace[trace_id].append((row.get("turn_index") or 0, float(score)))

    seg_sum = [0.0] * n_segments
    seg_count = [0] * n_segments
    deltas: list[float] = []
    for turns in by_trace.values():
        if len(turns) < 2:
            continue
        turns.sort(key=lambda item: item[0])
        k = len(turns)
        for rank, (_, score) in enumerate(turns):
            segment = min(int((rank / (k - 1)) * n_segments), n_segments - 1)
            seg_sum[segment] += score
            seg_count[segment] += 1
        third = max(1, k // 3)
        early = sum(score for _, score in turns[:third]) / third
        late = sum(score for _, score in turns[-third:]) / third
        deltas.append(late - early)

    means = [seg_sum[i] / seg_count[i] if seg_count[i] else None for i in range(n_segments)]
    multi = len(deltas)
    summary = {
        "multi_turn_traces": multi,
        "rising": sum(1 for d in deltas if d > 0),
        "falling": sum(1 for d in deltas if d < 0),
        "mean_delta": round(sum(deltas) / multi, 4) if multi else None,
    }
    return means, summary


def _drift_curve(
    audited_rows: Sequence[Mapping[str, Any]],
    reference_rows: Sequence[Mapping[str, Any]],
    *,
    n_segments: int = DRIFT_SEGMENTS,
) -> dict[str, Any]:
    """Start->end trait trajectory for audited vs reference, averaged corpus-wide."""

    audited_means, audited_summary = _segment_means(audited_rows, n_segments)
    reference_means, reference_summary = _segment_means(reference_rows, n_segments)
    labels = (
        DRIFT_SEGMENT_LABELS if n_segments == len(DRIFT_SEGMENT_LABELS) else [f"Seg {i + 1}" for i in range(n_segments)]
    )
    segments = [
        {
            "position": round((i + 0.5) / n_segments, 3),
            "label": labels[i],
            "audited": round(audited_means[i], 5) if audited_means[i] is not None else None,
            "reference": round(reference_means[i], 5) if reference_means[i] is not None else None,
        }
        for i in range(n_segments)
    ]
    return {
        "segments": segments,
        "audited_summary": audited_summary,
        "reference_summary": reference_summary,
        "n_segments": n_segments,
    }


def character_report(provider: str | None = None) -> dict[str, Any]:
    """Frequency x distinctiveness over persona traits for one audited provider."""

    audited_provider = resolve_provider(provider)
    coordinates = candidate_coordinates()
    audited_rows = score_rows_for_coordinates(coordinates, provider=audited_provider) or []

    track_info = track_group_map(audited_provider)
    if track_info and CHARACTER_CONTROL_TRACK in track_info[0]:
        return _track_character_report(audited_provider, audited_rows, track_info)

    reference_provider = CHARACTER_REFERENCE_PROVIDER
    reference_rows = score_rows_for_coordinates(coordinates, provider=reference_provider) or []
    result = compute_character(reference_rows, audited_rows)
    result["meta"].update(
        {
            "audited_provider": audited_provider,
            "reference_provider": reference_provider,
            "self_reference": audited_provider == reference_provider,
            "concern_traits": list(CHARACTER_CONCERN_TRAITS),
        }
    )
    return result


def _track_character_report(
    audited_provider: str,
    audited_rows: Sequence[Mapping[str, Any]],
    track_info: tuple[list[str], dict[str, str]],
) -> dict[str, Any]:
    """Control track as the reference; every other track audited against it.

    Per-track points are raw score magnitudes: each persona's mean raw trait
    score, the control's mean, and the signed delta between them — never
    present-rates or threshold-crossing counts (see _group_score_means). The
    pooled compute exists only to carry the per-track means for the heatmap.
    """

    order, groups = track_info

    def rows_for(track: str) -> list[Mapping[str, Any]]:
        return [row for row in audited_rows if groups.get(str(row.get("trace_id") or "")) == track]

    control_rows = rows_for(CHARACTER_CONTROL_TRACK)
    result = compute_character(control_rows, audited_rows, audited_groups=groups, group_order=order)
    control_stats = _per_trace_stats(control_rows)
    result["track_reports"] = [
        {"track": track, "points": _raw_delta_points(_per_trace_stats(rows_for(track)), control_stats)}
        for track in order
        if track != CHARACTER_CONTROL_TRACK
    ]
    result["meta"].update(
        {
            "audited_provider": audited_provider,
            "reference_provider": CHARACTER_CONTROL_TRACK,
            "reference_kind": "track",
            "self_reference": False,
            "concern_traits": list(CHARACTER_CONCERN_TRAITS),
        }
    )
    return result


def _raw_delta_points(
    track_stats: Mapping[str, Mapping[str, Mapping[str, Any]]],
    control_stats: Mapping[str, Mapping[str, Mapping[str, Any]]],
) -> list[dict[str, Any]]:
    """Raw-magnitude points per trait: track mean, control mean, signed delta."""

    points: list[dict[str, Any]] = []
    for coordinate in sorted(set(track_stats) & set(control_stats)):
        if not coordinate.startswith(PERSONA_COORDINATE_PREFIX):
            continue
        track_traces = track_stats[coordinate]
        control_traces = control_stats[coordinate]
        if not track_traces or not control_traces:
            continue
        mean_score = _mean_of([stat["mean"] for stat in track_traces.values()])
        peak_mean = _mean_of([stat["max"] for stat in track_traces.values()])
        control_mean = _mean_of([stat["mean"] for stat in control_traces.values()])
        control_peak = _mean_of([stat["max"] for stat in control_traces.values()])
        points.append(
            {
                "coordinate": coordinate,
                "trait": trait_name(coordinate),
                "label": trait_label(coordinate),
                "mean_score": mean_score,
                "peak_mean": peak_mean,
                "control_mean_score": control_mean,
                "control_peak_mean": control_peak,
                "delta": round((mean_score or 0.0) - (control_mean or 0.0), 6),
                "peak_delta": round((peak_mean or 0.0) - (control_peak or 0.0), 6),
                "traces": len(track_traces),
            }
        )
    points.sort(key=lambda point: point["delta"], reverse=True)
    return points


def character_trait_detail(
    coordinate: str,
    provider: str | None = None,
    *,
    limit: int = TRAIT_DETAIL_TRACE_LIMIT,
) -> dict[str, Any] | None:
    """Audited traces where a trait is present, ranked by peak intensity.

    The funnel target: every row links into Session Review for turn-by-turn
    inspection of that specific trace. Returns ``None`` when the trait has no
    audited traces or no usable reference (a dropped trait has no drill-down).
    """

    if not coordinate or not coordinate.startswith(PERSONA_COORDINATE_PREFIX):
        return None

    audited_provider = resolve_provider(provider)
    track_info = track_group_map(audited_provider)
    if track_info and CHARACTER_CONTROL_TRACK in track_info[0]:
        return _track_trait_detail(coordinate, audited_provider, track_info, limit=limit)

    reference_provider = CHARACTER_REFERENCE_PROVIDER
    coordinates = (coordinate,)

    reference_rows = score_rows_for_coordinates(coordinates, provider=reference_provider) or []
    audited_rows = score_rows_for_coordinates(coordinates, provider=audited_provider) or []

    reference = _per_trace_stats(reference_rows).get(coordinate, {})
    audited = _per_trace_stats(audited_rows).get(coordinate, {})
    if not audited:
        return None

    reference_max = sorted(stat["max"] for stat in reference.values())
    if len(reference_max) < MIN_REFERENCE_TRACES:
        return None

    threshold = _quantile(reference_max, PRESENCE_QUANTILE)
    reference_present, reference_total = _present_rate(reference_max, threshold)
    reference_rate = reference_present / reference_total

    present_rows = [
        {
            "trace_id": trace_id,
            "max_score": round(stat["max"], 6),
            "mean_score": round(stat["mean"], 6),
            "peak_turn": stat["peak_turn"],
            "turns": stat["turns"],
        }
        for trace_id, stat in audited.items()
        if stat["max"] > threshold
    ]
    present_rows.sort(key=lambda row: row["max_score"], reverse=True)
    audited_present = len(present_rows)
    audited_total = len(audited)
    audited_rate = audited_present / audited_total

    audited_max = [stat["max"] for stat in audited.values()]
    distribution = _distribution_shift(audited_max, reference_max, threshold)
    drift = _drift_curve(audited_rows, reference_rows)

    return {
        "point": {
            "coordinate": coordinate,
            "trait": trait_name(coordinate),
            "label": trait_label(coordinate),
            "frequency": round(audited_rate, 4),
            "distinctiveness": round(audited_rate - reference_rate, 4),
            "reference_rate": round(reference_rate, 4),
            "threshold": round(threshold, 6),
            "audited_present": audited_present,
            "audited_total": audited_total,
            "reference_present": reference_present,
            "reference_total": reference_total,
        },
        "traces": present_rows[: max(limit, 0)] if limit else present_rows,
        "truncated": bool(limit) and audited_present > limit,
        "distribution": distribution,
        "drift": drift,
        "meta": {
            "audited_provider": audited_provider,
            "reference_provider": reference_provider,
            "presence_rule": "trace_max_gt_threshold",
        },
    }


def _track_trait_detail(
    coordinate: str,
    audited_provider: str,
    track_info: tuple[list[str], dict[str, str]],
    *,
    limit: int,
) -> dict[str, Any] | None:
    """Trait drill-down with the control track as reference.

    Distribution and drift come back as one series per track (control
    included) so the persona split is never pooled away; the trace table
    covers the audited (non-control) tracks and labels each row's track.
    """

    order, groups = track_info
    rows = score_rows_for_coordinates((coordinate,), provider=audited_provider) or []
    rows_by_track: dict[str, list[Mapping[str, Any]]] = {track: [] for track in order}
    for row in rows:
        rows_by_track.setdefault(groups.get(str(row.get("trace_id") or ""), "unknown"), []).append(row)

    reference = _per_trace_stats(rows_by_track.get(CHARACTER_CONTROL_TRACK, [])).get(coordinate, {})
    if len(reference) < MIN_REFERENCE_TRACES:
        return None
    control_mean = _mean_of([stat["mean"] for stat in reference.values()])
    control_peak = _mean_of([stat["max"] for stat in reference.values()])

    audited_tracks = [track for track in order if track != CHARACTER_CONTROL_TRACK]
    audited_rows = [row for track in audited_tracks for row in rows_by_track.get(track, [])]
    audited = _per_trace_stats(audited_rows).get(coordinate, {})
    if not audited:
        return None

    # Every audited trace, ranked by peak raw score — no threshold filter;
    # the comparison lives in the raw scores, not in a crossing count.
    trace_rows = [
        {
            "trace_id": trace_id,
            "track": groups.get(trace_id, "unknown"),
            "max_score": round(stat["max"], 6),
            "mean_score": round(stat["mean"], 6),
            "peak_turn": stat["peak_turn"],
            "turns": stat["turns"],
        }
        for trace_id, stat in audited.items()
    ]
    trace_rows.sort(key=lambda row: row["max_score"], reverse=True)

    series_max = {
        track: [stat["max"] for stat in _per_trace_stats(rows_by_track.get(track, [])).get(coordinate, {}).values()]
        for track in order
    }
    distribution = _distribution_shift_series(series_max, round(control_peak or 0.0, 6), order=order)
    drift = _drift_curve_series({track: rows_by_track.get(track, []) for track in order}, order=order)

    audited_mean = _mean_of([stat["mean"] for stat in audited.values()])
    audited_peak = _mean_of([stat["max"] for stat in audited.values()])
    return {
        "point": {
            "coordinate": coordinate,
            "trait": trait_name(coordinate),
            "label": trait_label(coordinate),
            "mean_score": audited_mean,
            "peak_mean": audited_peak,
            "control_mean_score": control_mean,
            "control_peak_mean": control_peak,
            "delta": round((audited_mean or 0.0) - (control_mean or 0.0), 6),
            "audited_total": len(audited),
        },
        "traces": trace_rows[: max(limit, 0)] if limit else trace_rows,
        "truncated": bool(limit) and len(trace_rows) > limit,
        "distribution": distribution,
        "drift": drift,
        "meta": {
            "audited_provider": audited_provider,
            "reference_provider": CHARACTER_CONTROL_TRACK,
            "reference_kind": "track",
            "tracks": list(order),
        },
    }


def _distribution_shift_series(
    series_values: Mapping[str, Sequence[float]],
    threshold: float,
    *,
    order: Sequence[str],
    n_bins: int = DISTRIBUTION_BINS,
) -> dict[str, Any]:
    """Shared-bin per-trace-max histogram, one density series per track."""

    all_values = [value for values in series_values.values() for value in values]
    lo = min(all_values)
    hi = max(all_values)
    width = (hi - lo) / n_bins if hi > lo else 1.0
    counts = {name: histogram_counts(series_values.get(name, []), lo, hi, n_bins) for name in order}
    totals = {name: len(series_values.get(name, [])) for name in order}
    bins = []
    for index in range(n_bins):
        x0 = lo + index * width
        entry: dict[str, Any] = {
            "x0": round(x0, 4),
            "x1": round(x0 + width, 4),
            "mid": round(x0 + width / 2, 4),
        }
        for name in order:
            entry[name] = round(counts[name][index] / totals[name], 5) if totals[name] else 0.0
        bins.append(entry)
    return {
        "bins": bins,
        "threshold": round(threshold, 6),
        "series": list(order),
        "totals": totals,
    }


def _drift_curve_series(
    rows_by_series: Mapping[str, Sequence[Mapping[str, Any]]],
    *,
    order: Sequence[str],
    n_segments: int = DRIFT_SEGMENTS,
) -> dict[str, Any]:
    """Start->end trait trajectory, one curve per track."""

    means = {}
    summaries = {}
    for name in order:
        series_means, series_summary = _segment_means(rows_by_series.get(name, []), n_segments)
        means[name] = series_means
        summaries[name] = series_summary
    labels = (
        DRIFT_SEGMENT_LABELS if n_segments == len(DRIFT_SEGMENT_LABELS) else [f"Seg {i + 1}" for i in range(n_segments)]
    )
    segments = []
    for i in range(n_segments):
        entry: dict[str, Any] = {"position": round((i + 0.5) / n_segments, 3), "label": labels[i]}
        for name in order:
            entry[name] = round(means[name][i], 5) if means[name][i] is not None else None
        segments.append(entry)
    return {
        "segments": segments,
        "series": list(order),
        "summaries": summaries,
        "n_segments": n_segments,
    }
