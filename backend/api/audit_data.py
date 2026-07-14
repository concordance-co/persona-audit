"""Report assembly for the behavior-audit dashboard.

This is the composition layer only. The pieces live in:

- backend.api.flags             lexical flags + module scoring
- backend.api.persona_analytics persona vectors, track comparison, outliers
- backend.api.session_analytics session/user list + detail view-models
- backend.api.scores            activation-score access (DB or bundled JSON)

The session/user entry points are re-exported here so backend.api.app keeps a
single import site for report-shaped payloads.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from backend.api.cache import data_cache
from backend.api.flags import (
    _active_modules,
    _module_slope,
    flags_for_trace,
    module_scores,
    module_summaries,
    overall_band,
    risk_band_for_trace,
    session_summary,
)
from backend.api.models import AuditTrace
from backend.api.persona_analytics import persona_overview
from backend.api.registry import provider_descriptor, resolve_provider
from backend.api.scores import score_inventory, score_surface
from backend.api.session_analytics import (
    audit_session,
    audit_sessions,
    audit_user,
    audit_users,
)
from backend.api.stats import avg as _avg
from backend.api.stats import histogram as _histogram
from backend.api.stats import pearson as _pearson
from backend.api.trace_source import load_product_traces

__all__ = [
    "audit_report",
    "audit_report_overview",
    "product_analytics_report",
    "audit_sessions",
    "audit_session",
    "audit_users",
    "audit_user",
]


def audit_report(provider: str | None = None) -> dict[str, Any]:
    return _audit_report_cached(resolve_provider(provider))


@data_cache(maxsize=4)
def _audit_report_cached(provider: str) -> dict[str, Any]:
    traces, dataset_name, source = load_product_traces(provider)
    descriptor = provider_descriptor(provider)
    flags = [flag for trace in traces for flag in flags_for_trace(trace)]
    scores = module_scores(traces, flags, provider=provider)
    modules = module_summaries(traces, flags, scores)
    return {
        "kind": "persona_audit_report",
        "dataset_name": dataset_name,
        "provider": descriptor,
        "score_source": score_inventory(provider=provider),
        "score_surface": score_surface(provider=provider),
        "trace_count": len(traces),
        "user_count": len({trace.user_id for trace in traces}),
        "domains": sorted({trace.domain for trace in traces}),
        "modules": modules,
        "module_scores": scores,
        "flagged_moments": flags,
        "traces": [trace.to_dict() for trace in traces],
        "overview": audit_overview(traces, flags, scores),
        "summary": {
            "overall_band": overall_band(flags, len(traces)),
            "flagged_moment_count": len(flags),
            "source": source,
        },
    }


def audit_report_overview(provider: str | None = None) -> dict[str, Any]:
    report = audit_report(provider)
    return {
        "kind": report["kind"],
        "dataset_name": report["dataset_name"],
        "provider": report["provider"],
        "score_source": report["score_source"],
        "score_surface": report["score_surface"],
        "trace_count": report["trace_count"],
        "user_count": report["user_count"],
        "domains": report["domains"],
        "modules": report["modules"],
        "overview": report["overview"],
        "summary": report["summary"],
    }


def product_analytics_report(provider: str | None = None) -> dict[str, Any]:
    return _product_analytics_report_cached(resolve_provider(provider))


@data_cache(maxsize=4)
def _product_analytics_report_cached(provider: str) -> dict[str, Any]:
    traces, dataset_name, source = load_product_traces(provider)
    return {
        "kind": "persona_audit_product_analytics",
        "dataset_name": dataset_name,
        "provider": provider_descriptor(provider),
        "score_source": score_inventory(provider=provider),
        "trace_count": len(traces),
        "user_count": len({trace.user_id for trace in traces}),
        "domains": sorted({trace.domain for trace in traces}),
        "persona_overview": persona_overview(traces, provider=provider),
        "summary": {"source": source},
    }


def audit_overview(
    traces: Sequence[AuditTrace],
    flags: Sequence[Mapping[str, Any]],
    scores: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    active_modules = _active_modules(scores)
    scores_by_module: dict[str, list[Mapping[str, Any]]] = {module: [] for module in active_modules}
    for score in scores:
        scores_by_module.setdefault(str(score["module"]), []).append(score)

    stats: dict[str, dict[str, Any]] = {}
    for module in active_modules:
        module_scores_ = scores_by_module.get(module, [])
        numeric = [float(score["score"]) for score in module_scores_]
        flagged = sum(1 for value in numeric if value > 0)
        stats[module] = {
            "avg_projection": round(sum(numeric) / max(len(numeric), 1), 4),
            "scored_sessions": len(numeric),
            "band_a_sessions": flagged,
            "band_a_pct": round(flagged / max(len(numeric), 1) * 100, 2),
        }

    monthly_buckets: dict[str, dict[str, dict[str, Any]]] = {}
    trace_index = {trace.trace_id: index for index, trace in enumerate(traces)}
    for score in scores:
        trace_id = str(score["trace_id"])
        trace = next((candidate for candidate in traces if candidate.trace_id == trace_id), None)
        if trace is None:
            continue
        month = _trace_month(trace, trace_index.get(trace_id, 0))
        bucket = monthly_buckets.setdefault(month, {})
        dim_bucket = bucket.setdefault(str(score["module"]), {"sum": 0.0, "n": 0, "band_a": 0})
        value = float(score["score"])
        dim_bucket["sum"] += value
        dim_bucket["n"] += 1
        if value > 0:
            dim_bucket["band_a"] += 1

    monthly: list[dict[str, Any]] = []
    for month in sorted(monthly_buckets):
        dims: dict[str, dict[str, Any]] = {}
        for module, bucket in monthly_buckets[month].items():
            total = int(bucket["n"])
            dims[module] = {
                "total": total,
                "mean_proj": round(float(bucket["sum"]) / max(total, 1), 4),
                "band_a": int(bucket["band_a"]),
                "band_a_pct": round(float(bucket["band_a"]) / max(total, 1) * 100, 2),
            }
        monthly.append({"month": month, "dims": dims})

    score_matrix: dict[str, dict[str, float]] = {trace.trace_id: {} for trace in traces}
    for score in scores:
        score_matrix.setdefault(str(score["trace_id"]), {})[str(score["module"])] = float(score["score"])
    common_trace_ids = [
        trace_id for trace_id, row in score_matrix.items() if all(module in row for module in active_modules)
    ]
    means_by_module = {
        module: [score_matrix[trace_id][module] for trace_id in common_trace_ids] for module in active_modules
    }

    correlation: dict[str, dict[str, float | None]] = {}
    for module in active_modules:
        correlation[module] = {}
        for other in active_modules:
            correlation[module][other] = (
                1.0 if module == other else _pearson(means_by_module[module], means_by_module[other])
            )

    flag_lookup = [dict(flag) for flag in flags]
    trace_lookup = {trace.trace_id: trace for trace in traces}
    recent_flagged: list[dict[str, Any]] = []
    for flag in sorted(
        flag_lookup, key=lambda item: (trace_index.get(str(item["trace_id"]), 0), int(item["turn_index"])), reverse=True
    ):
        trace = trace_lookup.get(str(flag["trace_id"]))
        if trace is None:
            continue
        recent_flagged.append(
            {
                "id": trace.trace_id,
                "user_id": trace.user_id,
                "session_index": trace_index.get(trace.trace_id, 0) + 1,
                "start_time": _trace_month(trace, trace_index.get(trace.trace_id, 0)),
                "turn_count": len(trace.turns),
                "flag_dimension": flag["module"],
                "flag_projection": flag["score"],
                "title": flag["title"],
                "severity": flag["severity"],
            }
        )
        if len(recent_flagged) >= 10:
            break

    session_rows = [session_summary(trace.to_dict(), flags) for trace in traces]
    return {
        "dimensions": active_modules,
        "total_sessions": len(traces),
        "flagged_users": len(
            {trace.user_id for trace in traces if any(flag["trace_id"] == trace.trace_id for flag in flags)}
        ),
        "stats": stats,
        "monthly": monthly,
        "recent_flagged": recent_flagged,
        "projection_histograms": {module: _histogram(means_by_module[module], n_bins=8) for module in active_modules},
        "drift_histograms": {
            module: _histogram([_module_slope(trace, flags, module) for trace in traces], n_bins=8)
            for module in active_modules
        },
        "correlation": correlation,
        "correlation_n": len(common_trace_ids),
        "domain_mix": _count_rows(row["domain"] for row in session_rows),
        "risk_mix": _count_rows(row["risk_band"] for row in session_rows),
        "top_users": _top_user_rows([trace.to_dict() for trace in traces], flags)[:6],
    }


def _trace_month(trace: AuditTrace, index: int) -> str:
    for key in ("started_at", "start_time", "created_at", "timestamp"):
        value = trace.metadata.get(key)
        if isinstance(value, str) and len(value) >= 7:
            return value[:7]
    return f"2026-{min(index // 2 + 1, 12):02d}"


def _count_rows(values: Sequence[Any]) -> list[dict[str, Any]]:
    counts: dict[str, int] = {}
    for value in values:
        key = str(value)
        counts[key] = counts.get(key, 0) + 1
    return [{"name": key, "count": count} for key, count in sorted(counts.items())]


def _top_user_rows(traces: Sequence[Mapping[str, Any]], flags: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    by_user: dict[str, list[Mapping[str, Any]]] = {}
    for trace in traces:
        by_user.setdefault(str(trace["user_id"]), []).append(trace)
    rows: list[dict[str, Any]] = []
    for user_id, user_traces in by_user.items():
        trace_ids = {str(trace["trace_id"]) for trace in user_traces}
        user_flags = [flag for flag in flags if flag["trace_id"] in trace_ids]
        rows.append(
            {
                "user_id": user_id,
                "session_count": len(user_traces),
                "domains": sorted({str(trace["domain"]) for trace in user_traces}),
                "flag_count": len(user_flags),
                "high_risk_sessions": sum(
                    1 for trace in user_traces if risk_band_for_trace(str(trace["trace_id"]), flags) == "high"
                ),
                "avg_reward": _avg(trace.get("reward") for trace in user_traces),
            }
        )
    rows.sort(key=lambda row: (row["high_risk_sessions"], row["flag_count"], row["session_count"]), reverse=True)
    return rows
