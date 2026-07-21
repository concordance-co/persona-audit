"""Session and user view-models: list/detail payloads for the dashboard.

Composes traces (backend.api.trace_source), lexical flags (backend.api.flags),
and activation scores (backend.api.scores) into the /api/audit/sessions and
/api/audit/users payloads, including per-session deviation analytics.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from backend.api.cache import data_cache
from backend.api.flags import risk_band_for_trace, session_summary
from backend.api.persona_analytics import (
    EMOTION_CLUSTER_VECTORS,
    PERSONA_VECTOR_NAMES,
    _baseline_scope_label,
    _basis_value,
    _empty_basis,
    _overview_vectors,
    _percentile,
    _persona_records,
    _persona_turn_records,
    _persona_vector_primary_coordinate,
    _preferred_session_scope,
    _quintile_band,
    _round_or_none,
    _top_z_items,
    _turn_baseline_key,
    _workflow_outliers,
    compute_basis,
    group_summary,
)
from backend.api.registry import provider_descriptor, resolve_provider
from backend.api.scores import (
    real_score_details,
    real_score_summary,
)
from backend.api.stats import as_float as _as_float
from backend.api.stats import avg as _avg
from backend.api.stats import quantile as _quantile
from backend.api.trace_source import load_product_traces


def _audit_report(provider: str | None = None) -> dict:
    # Imported lazily: backend.api.audit_data composes this module, so a
    # top-level import here would be circular. The report is the cached,
    # provider-resolved source of session rows and flags.
    from backend.api.audit_data import audit_report

    return audit_report(provider)


def audit_sessions(
    *, domain: str | None = None, risk: str | None = None, provider: str | None = None
) -> list[dict[str, Any]]:
    report = _audit_report(provider)
    flags = report["flagged_moments"]
    signals = _session_signals(resolve_provider(provider))
    rows = [
        {**session_summary(trace, flags), "signal": signals.get(str(trace["trace_id"]))} for trace in report["traces"]
    ]
    if domain:
        rows = [row for row in rows if row["domain"] == domain]
    if risk:
        rows = [row for row in rows if row["risk_band"] == risk]
    rows.sort(key=_session_sort_key, reverse=True)
    return rows


def _session_sort_key(row: Mapping[str, Any]) -> tuple[float, int, int]:
    """Rank by activation evidence, then lexical risk and flag count."""

    risk_order = {"high": 2, "mid": 1, "low": 0}
    return (
        float((row.get("signal") or {}).get("outlier_score") or 0.0),
        risk_order.get(str(row.get("risk_band") or "low"), 0),
        int(row.get("flag_count") or 0),
    )


@data_cache(maxsize=4)
def _session_signals(provider: str) -> dict[str, dict[str, Any]]:
    """Strongest activation signal per trace, for ranking the sessions list.

    Reuses the workflow-outlier ranking (RMS z per family within the trace's
    workflow); each trace keeps its higher-scoring family row.
    """

    best: dict[str, dict[str, Any]] = {}
    for row in _workflow_outliers(_persona_records_for_product(provider)):
        trace_id = str(row["trace_id"])
        current = best.get(trace_id)
        if current is not None and float(current["outlier_score"]) >= float(row["outlier_score"]):
            continue
        top = (row.get("top_z") or [{}])[0]
        best[trace_id] = {
            "outlier_score": row["outlier_score"],
            "family": row["family"],
            "vector": top.get("vector"),
            "coordinate": top.get("coordinate"),
            "z": top.get("z"),
            "polarity": top.get("polarity"),
            "baseline_scope": row["baseline_scope"],
        }
    return best


def audit_session(trace_id: str, provider: str | None = None) -> dict[str, Any] | None:
    report = _audit_report(provider)
    traces = {trace["trace_id"]: trace for trace in report["traces"]}
    trace = traces.get(trace_id)
    if trace is None:
        return None
    flags = [flag for flag in report["flagged_moments"] if flag["trace_id"] == trace_id]
    scores = [score for score in report["module_scores"] if score["trace_id"] == trace_id]
    resolved = resolve_provider(provider)
    score_details = real_score_details(trace_id, provider=resolved)
    score_summary = real_score_summary(trace_id, provider=resolved)
    return {
        "session": session_summary(trace, report["flagged_moments"]),
        "trace": trace,
        "provider": report["provider"],
        "flags": flags,
        "module_scores": scores,
        "score_details": score_details,
        "score_summary": score_summary,
        "projection_thresholds": report.get("score_surface", {}).get("projection_thresholds", []),
        "session_analytics": session_analytics(
            trace_id, score_summary, report.get("score_surface", {}), provider=resolved
        ),
    }


def audit_users(provider: str | None = None) -> list[dict[str, Any]]:
    report = _audit_report(provider)
    flags = report["flagged_moments"]
    traces = report["traces"]
    by_user: dict[str, list[dict[str, Any]]] = {}
    for trace in traces:
        by_user.setdefault(trace["user_id"], []).append(trace)
    rows: list[dict[str, Any]] = []
    for user_id, user_traces in sorted(by_user.items()):
        trace_ids = {trace["trace_id"] for trace in user_traces}
        user_flags = [flag for flag in flags if flag["trace_id"] in trace_ids]
        rows.append(
            {
                "user_id": user_id,
                "session_count": len(user_traces),
                "domains": sorted({trace["domain"] for trace in user_traces}),
                "flag_count": len(user_flags),
                "high_risk_sessions": sum(
                    1 for trace in user_traces if risk_band_for_trace(trace["trace_id"], flags) == "high"
                ),
                "avg_reward": _avg(trace.get("reward") for trace in user_traces),
                "last_outcome": user_traces[-1]["outcome"],
            }
        )
    rows.sort(key=lambda row: (row["high_risk_sessions"], row["flag_count"], row["session_count"]), reverse=True)
    return rows


def audit_user(user_id: str, provider: str | None = None) -> dict[str, Any] | None:
    sessions = [row for row in audit_sessions(provider=provider) if row["user_id"] == user_id]
    if not sessions:
        return None
    return {
        "user": next(row for row in audit_users(provider=provider) if row["user_id"] == user_id),
        "sessions": sessions,
        "provider": provider_descriptor(provider),
    }


def session_analytics(
    trace_id: str,
    score_summary: Mapping[str, Any],
    score_surface_: Mapping[str, Any],
    provider: str | None = None,
) -> dict[str, Any]:
    records = _persona_records_for_product(resolve_provider(provider))
    record = next((row for row in records if str(row.get("trace_id")) == trace_id), None)
    if record is None:
        return {
            "available": False,
            "emotion_clusters": _session_emotion_cluster_rows(score_summary, score_surface_),
            "product_groups": {},
            "vector_deviations": [],
        }

    return {
        "available": True,
        "product_groups": _session_product_groups(record, records),
        "emotion_clusters": _session_emotion_cluster_rows(score_summary, score_surface_),
        "vector_deviations": (vector_deviations := _session_vector_deviations(record, records)),
        "investigation": _session_investigation(record, vector_deviations),
        "turn_deviations": _session_turn_deviations(trace_id, records, provider=provider),
    }


@data_cache(maxsize=4)
def _persona_records_for_product(provider: str) -> list[dict[str, Any]]:
    traces, _, _ = load_product_traces(provider)
    return _persona_records(traces, provider=provider)


def _session_product_groups(record: Mapping[str, Any], records: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    workflow = str(record.get("workflow") or "unknown")
    final_action = str(record.get("final_action") or "no final action")
    task_id = str(record.get("task_id") or "")
    workflow_group = [row for row in records if str(row.get("workflow")) == workflow]
    action_group = [row for row in records if str(row.get("final_action")) == final_action]
    workflow_action_group = [
        row for row in records if str(row.get("workflow")) == workflow and str(row.get("final_action")) == final_action
    ]
    task_group = [row for row in records if str(row.get("task_id")) == task_id]
    return {
        "task_group": workflow,
        "final_action": final_action,
        "task_id": task_id,
        "outcome": record.get("outcome"),
        "reward": record.get("reward"),
        "turn_count": record.get("turn_count"),
        "global": group_summary("All sessions", records),
        "task_group_summary": group_summary(workflow, workflow_group),
        "final_action_summary": group_summary(final_action, action_group),
        "task_action_summary": group_summary(f"{workflow} / {final_action}", workflow_action_group),
        "repeated_task_summary": group_summary(task_id, task_group),
        "repeated_task_rewards": [float(row.get("reward") or 0.0) for row in task_group],
    }


def _session_emotion_cluster_rows(
    score_summary: Mapping[str, Any],
    score_surface_: Mapping[str, Any],
) -> list[dict[str, Any]]:
    surface_by_coordinate = {
        str(row.get("coordinate")): row
        for row in score_surface_.get("emotion_cluster_bands", [])
        if isinstance(row, Mapping)
    }
    rows: list[dict[str, Any]] = []
    cluster_rows = score_summary.get("emotion_clusters", [])
    if not cluster_rows:
        cluster_rows = score_surface_.get("emotion_clusters", [])
    for row in cluster_rows:
        if not isinstance(row, Mapping):
            continue
        coordinate = str(row.get("coordinate") or "")
        session_mean = _as_float(row.get("mean"))
        if not coordinate or session_mean is None:
            continue
        surface = surface_by_coordinate.get(coordinate, {})
        rows.append(
            {
                "coordinate": coordinate,
                "session_mean": round(session_mean, 6),
                "global_mean": _round_or_none(surface.get("mean")),
                "global_min": _round_or_none(surface.get("min")),
                "global_max": _round_or_none(surface.get("max")),
                "q20": _round_or_none(surface.get("q20")),
                "q40": _round_or_none(surface.get("q40")),
                "q60": _round_or_none(surface.get("q60")),
                "q80": _round_or_none(surface.get("q80")),
                "rows": int(row.get("rows") or row.get("n") or 0),
                "percentile_band": _quintile_band(session_mean, surface),
                "member_coordinates": list(row.get("member_coordinates") or surface.get("member_coordinates") or []),
            }
        )
    rows.sort(key=lambda item: abs(float(item["session_mean"])), reverse=True)
    return rows


def _session_vector_deviations(
    record: Mapping[str, Any],
    records: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    workflow = str(record.get("workflow") or "unknown")
    final_action = str(record.get("final_action") or "no final action")
    task_id = str(record.get("task_id") or "")
    cohorts = {
        "global": list(records),
        "workflow": [row for row in records if str(row.get("workflow")) == workflow],
        "task_group": [row for row in records if str(row.get("workflow")) == workflow],
        "final_action": [row for row in records if str(row.get("final_action")) == final_action],
        "task_action": [
            row
            for row in records
            if str(row.get("workflow")) == workflow and str(row.get("final_action")) == final_action
        ],
        "repeated_task": [row for row in records if str(row.get("task_id")) == task_id],
    }
    bases = {scope: compute_basis(cohort, PERSONA_VECTOR_NAMES) for scope, cohort in cohorts.items()}
    rows: list[dict[str, Any]] = []
    for vector in PERSONA_VECTOR_NAMES:
        session_value = _basis_value(record, vector)
        display_value = _as_float(record.get(vector))
        raw_value = _as_float(record.get(f"{vector}_raw"))
        if session_value is None:
            continue
        global_values = [
            value for value in (_basis_value(candidate, vector) for candidate in cohorts["global"]) if value is not None
        ]
        scope_rows: dict[str, dict[str, Any]] = {}
        for scope, basis in bases.items():
            stats = dict(basis.get(vector) or _empty_basis(vector))
            mean_value = _as_float(stats.get("mean"))
            sd_value = _as_float(stats.get("sd"))
            delta = session_value - mean_value if mean_value is not None else None
            stats["scope"] = scope
            stats["label"] = _baseline_scope_label(scope, record)
            stats["delta"] = round(delta, 6) if delta is not None else None
            stats["z"] = round(delta / sd_value, 6) if delta is not None and sd_value else None
            scope_rows[scope] = stats
        expected_scope, fallback_reason = _preferred_session_scope(scope_rows)
        expected = scope_rows[expected_scope]
        expected_mean = _as_float(expected.get("mean"))
        expected_sd = _as_float(expected.get("sd"))
        delta = session_value - expected_mean if expected_mean is not None else None
        rows.append(
            {
                "vector": vector,
                "coordinate": _persona_vector_primary_coordinate(vector),
                "family": "emotion_cluster" if vector in EMOTION_CLUSTER_VECTORS else "persona",
                "session": round(session_value, 6),
                "display_session": round(display_value, 6) if display_value is not None else None,
                "raw_session": round(raw_value, 6) if raw_value is not None else None,
                "global": scope_rows["global"],
                "workflow": scope_rows["workflow"],
                "task_group": scope_rows["workflow"],
                "final_action": scope_rows["final_action"],
                "task_action": scope_rows["task_action"],
                "repeated_task": scope_rows["repeated_task"],
                "scopes": scope_rows,
                "expected_scope": expected_scope,
                "expected_label": expected.get("label"),
                "expected_mean": round(expected_mean, 6) if expected_mean is not None else None,
                "expected_n": int(expected.get("n") or 0),
                "delta": round(delta, 6) if delta is not None else None,
                "z": round(delta / expected_sd, 6) if delta is not None and expected_sd else None,
                "polarity": "low" if delta is not None and delta < 0 else "high",
                "fallback_reason": fallback_reason,
                "global_percentile": round(_percentile(global_values, session_value), 6) if global_values else None,
            }
        )
    rows.sort(
        key=lambda row: abs(float(row.get("z") if row.get("z") is not None else row.get("delta") or 0.0)), reverse=True
    )
    return rows


def _session_investigation(record: Mapping[str, Any], deviations: Sequence[Mapping[str, Any]]) -> dict[str, Any] | None:
    overview = set(_overview_vectors())
    selected = next((row for row in deviations if row.get("vector") in overview and row.get("z") is not None), None)
    if selected is None:
        selected = next((row for row in deviations if row.get("z") is not None), None)
    if selected is None:
        return None
    return _session_investigation_from_deviation(record, selected, str(selected.get("expected_scope") or "global"))


def _session_investigation_from_deviation(
    record: Mapping[str, Any],
    deviation: Mapping[str, Any],
    baseline_scope: str,
) -> dict[str, Any]:
    scopes = deviation.get("scopes") if isinstance(deviation.get("scopes"), Mapping) else {}
    scope = scopes.get(baseline_scope) if isinstance(scopes.get(baseline_scope), Mapping) else deviation
    z = _as_float(scope.get("z"))
    delta = _as_float(scope.get("delta"))
    vector = str(deviation.get("vector") or "")
    return {
        "trace_id": record.get("trace_id"),
        "vector": vector,
        "coordinate": deviation.get("coordinate"),
        "family": deviation.get("family"),
        "polarity": "low" if (z is not None and z < 0) or (z is None and delta is not None and delta < 0) else "high",
        "baseline_scope": baseline_scope,
        "baseline_label": scope.get("label") or _baseline_scope_label(baseline_scope, record),
        "baseline_n": int(scope.get("n") or 0),
        "baseline_mean": scope.get("mean"),
        "baseline_sd": scope.get("sd"),
        "observed": deviation.get("session"),
        "display_observed": deviation.get("display_session"),
        "raw_observed": deviation.get("raw_session"),
        "delta": scope.get("delta"),
        "z": scope.get("z"),
        "fallback_reason": deviation.get("fallback_reason")
        if baseline_scope == deviation.get("expected_scope")
        else None,
    }


def _session_turn_deviations(
    trace_id: str, records: Sequence[Mapping[str, Any]], provider: str | None = None
) -> list[dict[str, Any]]:
    turn_records = _persona_turn_records(records, provider=provider)
    if not turn_records:
        return []
    selected = _overview_vectors()
    length_values = sorted({int(record.get("turn_count") or 0) for record in records})
    length_thresholds = [_quantile(length_values, q) for q in (0.25, 0.5, 0.75)] if length_values else [0.0, 0.0, 0.0]
    bucketed_turns: dict[tuple[int, int], list[Mapping[str, Any]]] = {}
    for record in turn_records:
        bucketed_turns.setdefault(_turn_baseline_key(record, length_thresholds), []).append(record)
    baseline_by_key = {key: compute_basis(bucket_records, selected) for key, bucket_records in bucketed_turns.items()}
    rows: list[dict[str, Any]] = []
    for record in turn_records:
        if str(record.get("trace_id")) != trace_id:
            continue
        key = _turn_baseline_key(record, length_thresholds)
        vector_rows: dict[str, dict[str, Any]] = {}
        z_scores: dict[str, float] = {}
        for vector in selected:
            value = _basis_value(record, vector)
            stats = baseline_by_key.get(key, {}).get(vector, {})
            mean_value = _as_float(stats.get("mean"))
            sd_value = _as_float(stats.get("sd"))
            if value is None or mean_value is None or not sd_value:
                continue
            z = (value - mean_value) / sd_value
            z_scores[vector] = z
            vector_rows[vector] = {
                "vector": vector,
                "coordinate": _persona_vector_primary_coordinate(vector),
                "family": "emotion_cluster" if vector in EMOTION_CLUSTER_VECTORS else "persona",
                "value": round(value, 6),
                "baseline_scope": "turn_position",
                "baseline_label": "length quartile + relative turn position",
                "baseline_n": int(stats.get("n") or 0),
                "baseline_mean": stats.get("mean"),
                "baseline_sd": stats.get("sd"),
                "z": round(z, 6),
                "polarity": "low" if z < 0 else "high",
            }
        rows.append(
            {
                "turn_index": int(record.get("turn_index") or 0),
                "relative_position": round(float(record.get("relative_position") or 0.0), 4),
                "baseline_key": list(key),
                "vectors": vector_rows,
                "top_z": _top_z_items(z_scores, limit=3),
            }
        )
    rows.sort(key=lambda row: int(row.get("turn_index") or 0))
    return rows
