"""Public score-access entry points for the serving layer.

Resolution order for every accessor: the configured Postgres tables when a
database URL is set, else the bundled offline caches (data/score_summaries/,
data/supplemental_scores/). Providers select run ids and tables via their
ScoreConfig (backend.api.registry).
"""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from typing import Any

import psycopg
from psycopg.rows import dict_row

from backend.api.cache import data_cache
from backend.api.models import AuditTrace
from backend.api.score_cache import _read_score_summary_cache, _write_score_summary_cache
from backend.api.scores.emotion_clusters import (
    SELECTED_SESSION_EMOTIONS,
    _emotion_cluster_stats_for_rows,
)
from backend.api.scores.offline import (
    _append_missing_supplemental_rows,
    _merge_supplemental_inventory,
    _merge_supplemental_score_surface,
    _supplemental_score_rows,
    _supplemental_score_rows_for_coordinates,
    _supplemental_score_rows_for_trace,
)
from backend.api.scores.provider_context import (
    _CURRENT_PROVIDER,
    current_score_run_id,
    current_score_table,
    database_url,
    normalized_score_provider,
)
from backend.api.scores.shaping import (
    _coordinate_stats,
    _high_stakes_probability,
    _high_stakes_probe_stats,
)
from backend.api.scores.sql_summaries import _build_score_summary, _read_score_summary_table

_score_run_id = current_score_run_id
_score_table = current_score_table
_database_url = database_url
_normalized_score_provider = normalized_score_provider

logger = logging.getLogger(__name__)


def real_module_scores(traces: Sequence[AuditTrace], provider: str | None = None) -> list[dict[str, Any]] | None:
    summary = score_summary(provider=provider)
    if summary is None:
        return None
    rows = summary.get("module_scores")
    if not isinstance(rows, Sequence):
        return None
    by_trace: dict[str, list[Mapping[str, Any]]] = {}
    for row in rows:
        if isinstance(row, Mapping) and row.get("trace_id"):
            by_trace.setdefault(str(row["trace_id"]), []).append(row)
    module_rows: list[dict[str, Any]] = []
    for trace in traces:
        module_rows.extend(dict(row) for row in by_trace.get(trace.trace_id, []))
    return module_rows


def real_score_details(trace_id: str, provider: str | None = None) -> list[dict[str, Any]]:
    trace_rows = score_rows_for_trace(trace_id, provider=provider)
    if trace_rows is None:
        return []
    return [
        {
            "artifact_id": row.get("artifact_id"),
            "score_family": row.get("score_family"),
            "coordinate": row.get("coordinate"),
            "example_key": row.get("example_key"),
            "turn_index": row.get("turn_index"),
            "layer": row.get("layer"),
            "score": row.get("score"),
            "probability": row.get("probability"),
            "high_stakes_probability": _high_stakes_probability(row),
            "prediction": row.get("prediction"),
            "positive_class": row.get("positive_class"),
            "row_payload": row.get("row_payload"),
        }
        for row in trace_rows
    ]


def real_score_summary(trace_id: str, provider: str | None = None) -> dict[str, Any]:
    trace_rows = score_rows_for_trace(trace_id, provider=provider)
    if trace_rows is None:
        return {"available": False}
    return {
        "available": True,
        "score_detail_count": len(trace_rows),
        "assistant_traits": _coordinate_stats(row for row in trace_rows if row.get("score_family") == "assistant_axis"),
        "top_emotions": _coordinate_stats(row for row in trace_rows if row.get("score_family") == "emotion")[:12],
        "selected_emotions": _coordinate_stats(
            row for row in trace_rows if row.get("coordinate") in SELECTED_SESSION_EMOTIONS
        ),
        "emotion_clusters": _emotion_cluster_stats_for_rows(trace_rows),
        "high_stakes_probes": _high_stakes_probe_stats(trace_rows),
    }


def score_surface(provider: str | None = None) -> dict[str, Any]:
    run_id = _score_run_id(provider)
    summary = score_summary(provider=provider)
    if summary is None:
        supplemental_rows = _supplemental_score_rows(run_id)
        if not supplemental_rows:
            return {"available": False}
        return _merge_supplemental_score_surface({"available": True}, supplemental_rows)
    surface = summary.get("score_surface")
    base = dict(surface) if isinstance(surface, Mapping) else {"available": False}
    return _merge_supplemental_score_surface(base, _supplemental_score_rows(run_id))


def score_inventory(provider: str | None = None) -> dict[str, Any]:
    run_id = _score_run_id(provider)
    summary = score_summary(provider=provider)
    if summary is None:
        supplemental_rows = _supplemental_score_rows(run_id)
        if not supplemental_rows:
            return {"available": False, "run_id": run_id, "families": []}
        return _merge_supplemental_inventory(
            {"available": True, "run_id": run_id, "families": []},
            supplemental_rows,
        )
    inventory = summary.get("score_inventory")
    base = dict(inventory) if isinstance(inventory, Mapping) else {"available": False, "run_id": run_id, "families": []}
    return _merge_supplemental_inventory(base, _supplemental_score_rows(run_id))


@data_cache(maxsize=4)
def score_summary(run_id: str | None = None, provider: str | None = None) -> dict[str, Any] | None:
    run_id = run_id or _score_run_id(provider)
    database_url = _database_url()
    if not database_url:
        return _read_score_summary_cache(run_id)
    token = _CURRENT_PROVIDER.set(_normalized_score_provider(provider))
    try:
        with psycopg.connect(database_url, row_factory=dict_row) as conn:
            summary = _read_score_summary_table(conn, run_id)
            if summary is None:
                summary = _build_score_summary(conn, run_id)
    except psycopg.Error as exc:
        logger.warning("score summary DB query failed; falling back to cached summary: %s", exc)
        return _read_score_summary_cache(run_id)
    finally:
        _CURRENT_PROVIDER.reset(token)
    _write_score_summary_cache(summary)
    return summary


@data_cache(maxsize=512)
def score_rows_for_trace(
    trace_id: str, run_id: str | None = None, provider: str | None = None
) -> list[dict[str, Any]] | None:
    run_id = run_id or _score_run_id(provider)
    supplemental_rows = _supplemental_score_rows_for_trace(trace_id, run_id)
    database_url = _database_url()
    if not database_url:
        return supplemental_rows or None
    token = _CURRENT_PROVIDER.set(_normalized_score_provider(provider))
    query = f"""
        SELECT
            artifact_id,
            score_family,
            coordinate,
            example_key,
            trace_id,
            turn_index,
            provider_id,
            source,
            domain,
            task_id,
            outcome,
            reward,
            is_high_stakes_candidate,
            source_model,
            user_model,
            layer,
            metric,
            score,
            probability,
            prediction,
            positive_class,
            slice_name,
            slice_index,
            slice_token_count,
            role,
            unit,
            summary,
            row_payload
        FROM {_score_table()}
        WHERE run_id = %s AND trace_id = %s
    """
    try:
        with psycopg.connect(database_url, row_factory=dict_row) as conn:
            rows = [dict(row) for row in conn.execute(query, (run_id, trace_id))]
            return _append_missing_supplemental_rows(rows, supplemental_rows)
    except psycopg.Error as exc:
        logger.warning("score rows DB query failed for trace %s; using supplemental only: %s", trace_id, exc)
        return supplemental_rows or None
    finally:
        _CURRENT_PROVIDER.reset(token)


@data_cache(maxsize=16)
def score_rows_for_coordinates(
    coordinates: tuple[str, ...], run_id: str | None = None, provider: str | None = None
) -> list[dict[str, Any]] | None:
    run_id = run_id or _score_run_id(provider)
    selected = tuple(sorted({coordinate for coordinate in coordinates if coordinate}))
    if not selected:
        return []
    supplemental_rows = _supplemental_score_rows_for_coordinates(selected, run_id)
    database_url = _database_url()
    if not database_url:
        return supplemental_rows or None
    token = _CURRENT_PROVIDER.set(_normalized_score_provider(provider))
    query = f"""
        SELECT
            score_family,
            coordinate,
            trace_id,
            turn_index,
            task_id,
            outcome,
            reward,
            score
        FROM {_score_table()}
        WHERE run_id = %s
            AND coordinate = ANY(%s)
            AND score IS NOT NULL
    """
    try:
        with psycopg.connect(database_url, row_factory=dict_row) as conn:
            rows = [dict(row) for row in conn.execute(query, (run_id, list(selected)))]
            return _append_missing_supplemental_rows(rows, supplemental_rows)
    except psycopg.Error:
        return supplemental_rows or None
    finally:
        _CURRENT_PROVIDER.reset(token)
