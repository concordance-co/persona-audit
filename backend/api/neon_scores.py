"""Neon-backed score access for Persona Audit."""

from __future__ import annotations

import ast
import json
import os
import re
from contextvars import ContextVar
from functools import lru_cache
from typing import Any, Iterable, Mapping, Sequence

import psycopg
from psycopg.rows import dict_row

from backend.api.models import AuditTrace
from backend.api.score_cache import (
    SCORE_SUMMARY_CACHE_DIR,
    SCORE_SUMMARY_CACHE_ENV,
    SCORE_SUMMARY_CACHE_VERSION,
    _read_score_summary_cache,
    _write_score_summary_cache,
)
from backend.paths import DATA_ROOT, DATABASE_URL_ENV, LEGACY_DATABASE_URL_ENV, configured_database_url, load_dotenv


DB_ENV_VAR = DATABASE_URL_ENV
LEGACY_DB_ENV_VAR = LEGACY_DATABASE_URL_ENV
DEFAULT_RUN_ID = "wr_667d470028fd_c294c37f"
SCORE_TABLE = "behavior_audit_tau2_score_rows"
SCORE_TABLE_ENV = "BEHAVIOR_AUDIT_SCORE_TABLE"
HERMES_SCORE_TABLE = "behavior_audit_hermes_score_rows"
HERMES_SCORE_TABLE_ENV = "BEHAVIOR_AUDIT_HERMES_SCORE_TABLE"
HERMES_SCORE_RUN_ID_ENV = "BEHAVIOR_AUDIT_HERMES_SCORE_RUN_ID"
HERMES_DEFAULT_RUN_ID = "behavior_audit_hermes_scoring_v1"
SCORE_SUMMARY_TABLE = "behavior_audit_score_summaries"
SCORE_SUMMARY_TABLE_ENV = "BEHAVIOR_AUDIT_SCORE_SUMMARY_TABLE"
SUPPLEMENTAL_SCORE_DIR = DATA_ROOT / "supplemental_scores"
EMOTION_CLUSTER_SCORE_FAMILY = "emotion_cluster"

NEGATIVE_AFFECT_COORDINATES = {
    "emotion__afraid",
    "emotion__alarmed",
    "emotion__angry",
    "emotion__annoyed",
    "emotion__anxious",
    "emotion__ashamed",
    "emotion__bitter",
    "emotion__distressed",
    "emotion__frustrated",
    "emotion__guilty",
    "emotion__helpless",
    "emotion__hopeless",
    "emotion__nervous",
    "emotion__overwhelmed",
    "emotion__panicked",
    "emotion__sad",
    "emotion__scared",
    "emotion__stressed",
    "emotion__upset",
    "emotion__worried",
}

SELECTED_SESSION_EMOTIONS = {
    "emotion__angry",
    "emotion__anxious",
    "emotion__calm",
    "emotion__frustrated",
    "emotion__sad",
    "emotion__worried",
}

_CURRENT_PROVIDER: ContextVar[str] = ContextVar("behavior_audit_score_provider", default="tau2")


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
        "assistant_traits": _coordinate_stats(
            row for row in trace_rows if row.get("score_family") == "assistant_axis"
        ),
        "top_emotions": _coordinate_stats(
            row for row in trace_rows if row.get("score_family") == "emotion"
        )[:12],
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


@lru_cache(maxsize=4)
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
    except psycopg.Error:
        return _read_score_summary_cache(run_id)
    finally:
        _CURRENT_PROVIDER.reset(token)
    _write_score_summary_cache(summary)
    return summary


@lru_cache(maxsize=512)
def score_rows_for_trace(trace_id: str, run_id: str | None = None, provider: str | None = None) -> list[dict[str, Any]] | None:
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
    except psycopg.Error:
        return supplemental_rows or None
    finally:
        _CURRENT_PROVIDER.reset(token)


@lru_cache(maxsize=16)
def score_rows_for_coordinates(coordinates: tuple[str, ...], run_id: str | None = None, provider: str | None = None) -> list[dict[str, Any]] | None:
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


def emotion_cluster_metadata() -> list[dict[str, Any]]:
    return _emotion_cluster_metadata()


def emotion_cluster_metadata_by_coordinate() -> dict[str, dict[str, Any]]:
    return _emotion_cluster_metadata_by_coordinate()


def _build_score_summary(conn: psycopg.Connection, run_id: str) -> dict[str, Any]:
    tail_stats = _summary_tail_stats(conn, run_id)
    return {
        "kind": "behavior_audit_score_summary",
        "version": SCORE_SUMMARY_CACHE_VERSION,
        "run_id": run_id,
        "score_inventory": _summary_score_inventory(conn, run_id),
        "module_scores": _summary_module_scores(conn, run_id),
        "score_surface": _summary_score_surface(conn, run_id, tail_stats),
    }


def _read_score_summary_table(conn: psycopg.Connection, run_id: str) -> dict[str, Any] | None:
    table_name = _score_summary_table()
    if not _table_exists(conn, table_name):
        return None
    row = conn.execute(
        f"""
        SELECT
            run_id,
            kind,
            version,
            score_inventory,
            score_surface,
            module_scores,
            payload
        FROM {table_name}
        WHERE run_id = %s
        """,
        (run_id,),
    ).fetchone()
    return _score_summary_from_table_row(row, run_id)


def _score_summary_from_table_row(row: Mapping[str, Any] | None, run_id: str) -> dict[str, Any] | None:
    if not row:
        return None
    payload = row.get("payload")
    if isinstance(payload, Mapping):
        candidate = dict(payload)
        candidate.setdefault("run_id", row.get("run_id"))
        candidate.setdefault("kind", row.get("kind"))
        candidate.setdefault("version", row.get("version"))
        candidate.setdefault("score_inventory", row.get("score_inventory") or {})
        candidate.setdefault("score_surface", row.get("score_surface") or {})
        candidate.setdefault("module_scores", row.get("module_scores") or [])
    else:
        candidate = {
            "kind": row.get("kind"),
            "version": row.get("version"),
            "run_id": row.get("run_id"),
            "score_inventory": row.get("score_inventory") or {},
            "score_surface": row.get("score_surface") or {},
            "module_scores": row.get("module_scores") or [],
        }
    if candidate.get("kind") != "behavior_audit_score_summary":
        return None
    if candidate.get("version") != SCORE_SUMMARY_CACHE_VERSION:
        return None
    if candidate.get("run_id") != run_id:
        return None
    if not isinstance(candidate.get("score_inventory"), Mapping):
        return None
    if not isinstance(candidate.get("score_surface"), Mapping):
        return None
    if not isinstance(candidate.get("module_scores"), Sequence):
        return None
    return candidate


def _summary_score_inventory(conn: psycopg.Connection, run_id: str) -> dict[str, Any]:
    query = f"""
        SELECT
            score_family,
            count(DISTINCT coordinate) AS coordinate_count,
            count(*) AS row_count
        FROM {_score_table()}
        WHERE run_id = %s
        GROUP BY score_family
        ORDER BY score_family
    """
    return {
        "available": True,
        "run_id": run_id,
        "families": [
            {
                "score_family": str(row["score_family"] or "unknown"),
                "coordinate_count": int(row["coordinate_count"]),
                "row_count": int(row["row_count"]),
            }
            for row in conn.execute(query, (run_id,))
        ],
    }


def _summary_module_scores(conn: psycopg.Connection, run_id: str) -> list[dict[str, Any]]:
    query = f"""
        WITH valued AS (
            SELECT
                trace_id,
                score_family,
                coordinate,
                score,
                CASE
                    WHEN score_family = 'high_stakes' AND probability IS NOT NULL AND positive_class = 'low-stakes' THEN 1.0 - probability
                    WHEN score_family = 'high_stakes' THEN probability
                    ELSE NULL
                END AS high_stakes_probability
            FROM {_score_table()}
            WHERE run_id = %s
        )
        SELECT
            trace_id,
            avg(score) FILTER (
                WHERE coordinate = 'assistant_axis_trait__sycophantic' AND score IS NOT NULL
            ) AS sycophancy,
            avg(high_stakes_probability) FILTER (
                WHERE score_family = 'high_stakes'
                    AND coordinate LIKE '%%domain_adapted_probe%%'
                    AND high_stakes_probability IS NOT NULL
            ) AS high_stakes_adapted,
            max(high_stakes_probability) FILTER (
                WHERE score_family = 'high_stakes' AND high_stakes_probability IS NOT NULL
            ) AS high_stakes_max,
            avg(score) FILTER (
                WHERE coordinate = ANY(%s) AND score IS NOT NULL
            ) AS negative_affect
        FROM valued
        WHERE trace_id IS NOT NULL
        GROUP BY trace_id
        ORDER BY trace_id
    """
    rows: list[dict[str, Any]] = []
    for row in conn.execute(query, (run_id, list(NEGATIVE_AFFECT_COORDINATES))):
        trace_id = str(row["trace_id"])
        high_stakes = _float_or_none(row["high_stakes_adapted"])
        if high_stakes is None:
            high_stakes = _float_or_none(row["high_stakes_max"])
        rows.extend(
            candidate
            for candidate in (
                _module_score("sycophancy", trace_id, _float_or_none(row["sycophancy"]), "assistant_axis_trait__sycophantic"),
                _module_score("high_stakes", trace_id, high_stakes, "adapted_probe_high_stakes_rate"),
                _module_score("emotion_posture", trace_id, _float_or_none(row["negative_affect"]), "negative_affect_emotion_projection"),
            )
            if candidate is not None
        )
    return rows


def _summary_score_surface(
    conn: psycopg.Connection,
    run_id: str,
    tail_stats: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    emotion_cluster_metadata = _emotion_cluster_metadata()
    emotion_cluster_stats = _summary_emotion_cluster_stats(conn, run_id)
    return {
        "available": True,
        "assistant_traits": _coordinate_stats_from_summary(tail_stats, score_family="assistant_axis"),
        "assistant_trait_bands": _coordinate_bands_from_summary(
            tail_stats,
            score_family="assistant_axis",
            exclude_coordinates={"assistant_axis"},
        ),
        "top_emotions": _coordinate_stats_from_summary(
            tail_stats,
            score_family="emotion",
            sort_by_pass_correlation=True,
        ),
        "emotion_bands": _coordinate_bands_from_summary(
            tail_stats,
            score_family="emotion",
            sort_by_pass_correlation=True,
        ),
        "emotion_cluster_metadata": emotion_cluster_metadata,
        "emotion_clusters": _coordinate_stats_from_summary(
            emotion_cluster_stats,
            score_family=EMOTION_CLUSTER_SCORE_FAMILY,
        ),
        "emotion_cluster_bands": _coordinate_bands_from_summary(
            emotion_cluster_stats,
            score_family=EMOTION_CLUSTER_SCORE_FAMILY,
        ),
        "negative_emotions": _coordinate_stats_from_summary(
            tail_stats,
            score_family="emotion",
            include_coordinates=NEGATIVE_AFFECT_COORDINATES,
        ),
        "high_stakes_probes": _summary_high_stakes_probe_stats(conn, run_id),
        "conversation_dynamics": _summary_conversation_dynamics(conn, run_id),
        "emotion_cluster_tail_explorer": _tail_explorer_from_summary(
            emotion_cluster_stats,
            _summary_emotion_cluster_histograms(conn, run_id),
            _summary_emotion_cluster_tail_rows(conn, run_id),
        ),
        "tail_explorer": _tail_explorer_from_summary(
            tail_stats,
            _summary_tail_histograms(conn, run_id),
            _summary_tail_rows(conn, run_id),
        ),
        "projection_thresholds": _projection_tail_thresholds_from_summary(tail_stats),
    }


def _summary_tail_stats(conn: psycopg.Connection, run_id: str) -> list[dict[str, Any]]:
    query = f"""
        WITH valued AS (
            SELECT
                score_family,
                coordinate,
                outcome,
                CASE
                    WHEN score_family = 'high_stakes' AND probability IS NOT NULL AND positive_class = 'low-stakes' THEN 1.0 - probability
                    WHEN score_family = 'high_stakes' THEN probability
                    ELSE score
                END AS value,
                CASE
                    WHEN outcome = 'pass' THEN 1.0
                    WHEN outcome = 'fail' THEN 0.0
                    ELSE NULL
                END AS pass_value
            FROM {_score_table()}
            WHERE run_id = %s
        )
        SELECT
            score_family,
            coordinate,
            count(*) AS rows,
            avg(value) AS mean,
            min(value) AS min,
            max(value) AS max,
            percentile_cont(0.05) WITHIN GROUP (ORDER BY value) AS q05,
            percentile_cont(0.20) WITHIN GROUP (ORDER BY value) AS q20,
            percentile_cont(0.40) WITHIN GROUP (ORDER BY value) AS q40,
            percentile_cont(0.50) WITHIN GROUP (ORDER BY value) AS q50,
            percentile_cont(0.60) WITHIN GROUP (ORDER BY value) AS q60,
            percentile_cont(0.80) WITHIN GROUP (ORDER BY value) AS q80,
            percentile_cont(0.95) WITHIN GROUP (ORDER BY value) AS q95,
            corr(value::double precision, pass_value::double precision) AS pass_correlation,
            count(pass_value) AS outcome_rows
        FROM valued
        WHERE value IS NOT NULL AND score_family IS NOT NULL AND coordinate IS NOT NULL
        GROUP BY score_family, coordinate
    """
    stats: list[dict[str, Any]] = []
    for row in conn.execute(query, (run_id,)):
        stats.append(
            {
                "score_family": str(row["score_family"]),
                "coordinate": str(row["coordinate"]),
                "rows": int(row["rows"]),
                "mean": round(float(row["mean"]), 6),
                "min": _round_or_none(row["min"]),
                "max": _round_or_none(row["max"]),
                "q05": _round_or_none(row["q05"]),
                "q20": _round_or_none(row["q20"]),
                "q40": _round_or_none(row["q40"]),
                "q50": _round_or_none(row["q50"]),
                "q60": _round_or_none(row["q60"]),
                "q80": _round_or_none(row["q80"]),
                "q95": _round_or_none(row["q95"]),
                "pass_correlation": _round_or_none(row["pass_correlation"]),
                "outcome_rows": int(row["outcome_rows"]),
            }
        )
    return stats


def _summary_tail_histograms(conn: psycopg.Connection, run_id: str, *, n_bins: int = 18) -> list[dict[str, Any]]:
    query = f"""
        WITH valued AS (
            SELECT
                score_family,
                coordinate,
                outcome,
                CASE
                    WHEN score_family = 'high_stakes' AND probability IS NOT NULL AND positive_class = 'low-stakes' THEN 1.0 - probability
                    WHEN score_family = 'high_stakes' THEN probability
                    ELSE score
                END AS value
            FROM {_score_table()}
            WHERE run_id = %s
        ),
        stats AS (
            SELECT score_family, coordinate, min(value) AS lo, max(value) AS hi
            FROM valued
            WHERE value IS NOT NULL
            GROUP BY score_family, coordinate
        ),
        binned AS (
            SELECT
                valued.score_family,
                valued.coordinate,
                stats.lo,
                stats.hi,
                valued.outcome,
                CASE
                    WHEN stats.lo = stats.hi THEN 0
                    ELSE LEAST(%s - 1, floor(((valued.value - stats.lo) / NULLIF(stats.hi - stats.lo, 0)) * %s)::int)
                END AS bin
            FROM valued
            JOIN stats USING (score_family, coordinate)
            WHERE valued.value IS NOT NULL
        )
        SELECT
            score_family,
            coordinate,
            lo,
            hi,
            bin,
            count(*) AS count,
            count(*) FILTER (WHERE outcome = 'pass') AS pass_count,
            count(*) FILTER (WHERE outcome IS DISTINCT FROM 'pass') AS fail_count
        FROM binned
        GROUP BY score_family, coordinate, lo, hi, bin
    """
    return [
        {
            "score_family": str(row["score_family"]),
            "coordinate": str(row["coordinate"]),
            "lo": float(row["lo"]),
            "hi": float(row["hi"]),
            "bin": int(row["bin"]),
            "count": int(row["count"]),
            "pass_count": int(row["pass_count"]),
            "fail_count": int(row["fail_count"]),
        }
        for row in conn.execute(query, (run_id, n_bins, n_bins))
    ]


def _summary_tail_rows(conn: psycopg.Connection, run_id: str, *, n_tail: int = 10) -> list[dict[str, Any]]:
    query = f"""
        WITH valued AS (
            SELECT
                score_family,
                coordinate,
                trace_id,
                turn_index,
                CASE
                    WHEN score_family = 'high_stakes' AND probability IS NOT NULL AND positive_class = 'low-stakes' THEN 1.0 - probability
                    WHEN score_family = 'high_stakes' THEN probability
                    ELSE score
                END AS value,
                domain,
                task_id,
                outcome,
                reward,
                role,
                summary
            FROM {_score_table()}
            WHERE run_id = %s
        ),
        ranked AS (
            SELECT
                *,
                row_number() OVER (PARTITION BY score_family, coordinate ORDER BY value DESC NULLS LAST) AS positive_rank,
                row_number() OVER (PARTITION BY score_family, coordinate ORDER BY value ASC NULLS LAST) AS negative_rank
            FROM valued
            WHERE value IS NOT NULL
        )
        SELECT
            score_family,
            coordinate,
            trace_id,
            turn_index,
            value,
            domain,
            task_id,
            outcome,
            reward,
            role,
            summary,
            positive_rank,
            negative_rank
        FROM ranked
        WHERE positive_rank <= %s OR negative_rank <= %s
    """
    return [
        {
            "score_family": str(row["score_family"]),
            "coordinate": str(row["coordinate"]),
            "trace_id": row.get("trace_id"),
            "turn_index": row.get("turn_index"),
            "value": float(row["value"]),
            "domain": row.get("domain"),
            "task_id": row.get("task_id"),
            "outcome": row.get("outcome"),
            "reward": row.get("reward"),
            "role": row.get("role"),
            "summary": row.get("summary"),
            "positive_rank": int(row["positive_rank"]),
            "negative_rank": int(row["negative_rank"]),
        }
        for row in conn.execute(query, (run_id, n_tail, n_tail))
    ]


def _summary_emotion_cluster_stats(conn: psycopg.Connection, run_id: str) -> list[dict[str, Any]]:
    query = f"""
        WITH cluster_members AS (
            SELECT *
            FROM jsonb_to_recordset(%s::jsonb) AS members(
                cluster_name text,
                cluster_coordinate text,
                member_concept text,
                member_coordinate text
            )
        ),
        cluster_values AS (
            SELECT
                cluster_members.cluster_name,
                cluster_members.cluster_coordinate,
                rows.example_key,
                rows.trace_id,
                rows.turn_index,
                avg(rows.score) AS value,
                max(rows.outcome) AS outcome,
                count(DISTINCT cluster_members.member_coordinate) AS matched_member_count
            FROM {_score_table()} AS rows
            JOIN cluster_members ON cluster_members.member_coordinate = rows.coordinate
            WHERE rows.run_id = %s
                AND rows.score_family = 'emotion'
                AND rows.score IS NOT NULL
            GROUP BY
                cluster_members.cluster_name,
                cluster_members.cluster_coordinate,
                rows.example_key,
                rows.trace_id,
                rows.turn_index
        )
        SELECT
            cluster_name,
            cluster_coordinate AS coordinate,
            count(*) AS rows,
            avg(value) AS mean,
            min(value) AS min,
            max(value) AS max,
            percentile_cont(0.05) WITHIN GROUP (ORDER BY value) AS q05,
            percentile_cont(0.20) WITHIN GROUP (ORDER BY value) AS q20,
            percentile_cont(0.40) WITHIN GROUP (ORDER BY value) AS q40,
            percentile_cont(0.50) WITHIN GROUP (ORDER BY value) AS q50,
            percentile_cont(0.60) WITHIN GROUP (ORDER BY value) AS q60,
            percentile_cont(0.80) WITHIN GROUP (ORDER BY value) AS q80,
            percentile_cont(0.95) WITHIN GROUP (ORDER BY value) AS q95,
            corr(
                value::double precision,
                CASE
                    WHEN outcome = 'pass' THEN 1.0
                    WHEN outcome = 'fail' THEN 0.0
                    ELSE NULL
                END::double precision
            ) AS pass_correlation,
            count(*) FILTER (WHERE outcome IN ('pass', 'fail')) AS outcome_rows,
            min(matched_member_count) AS min_matched_members,
            max(matched_member_count) AS max_matched_members
        FROM cluster_values
        GROUP BY cluster_name, cluster_coordinate
    """
    metadata = _emotion_cluster_metadata_by_coordinate()
    rows: list[dict[str, Any]] = []
    for row in conn.execute(query, (_emotion_cluster_mapping_json(), run_id)):
        coordinate = str(row["coordinate"])
        rows.append(
            {
                "score_family": EMOTION_CLUSTER_SCORE_FAMILY,
                "coordinate": coordinate,
                "cluster": str(row["cluster_name"]),
                "rows": int(row["rows"]),
                "mean": round(float(row["mean"]), 6),
                "min": _round_or_none(row["min"]),
                "max": _round_or_none(row["max"]),
                "q05": _round_or_none(row["q05"]),
                "q20": _round_or_none(row["q20"]),
                "q40": _round_or_none(row["q40"]),
                "q50": _round_or_none(row["q50"]),
                "q60": _round_or_none(row["q60"]),
                "q80": _round_or_none(row["q80"]),
                "q95": _round_or_none(row["q95"]),
                "pass_correlation": _round_or_none(row["pass_correlation"]),
                "outcome_rows": int(row["outcome_rows"]),
                "members": metadata.get(coordinate, {}).get("members", []),
                "member_coordinates": metadata.get(coordinate, {}).get("member_coordinates", []),
                "member_count": int(metadata.get(coordinate, {}).get("member_count", 0)),
                "min_matched_members": int(row["min_matched_members"]),
                "max_matched_members": int(row["max_matched_members"]),
            }
        )
    return rows


def _summary_emotion_cluster_histograms(conn: psycopg.Connection, run_id: str, *, n_bins: int = 18) -> list[dict[str, Any]]:
    query = f"""
        WITH cluster_members AS (
            SELECT *
            FROM jsonb_to_recordset(%s::jsonb) AS members(
                cluster_name text,
                cluster_coordinate text,
                member_concept text,
                member_coordinate text
            )
        ),
        cluster_values AS (
            SELECT
                cluster_members.cluster_coordinate,
                rows.example_key,
                rows.trace_id,
                rows.turn_index,
                avg(rows.score) AS value,
                max(rows.outcome) AS outcome
            FROM {_score_table()} AS rows
            JOIN cluster_members ON cluster_members.member_coordinate = rows.coordinate
            WHERE rows.run_id = %s
                AND rows.score_family = 'emotion'
                AND rows.score IS NOT NULL
            GROUP BY cluster_members.cluster_coordinate, rows.example_key, rows.trace_id, rows.turn_index
        ),
        stats AS (
            SELECT cluster_coordinate, min(value) AS lo, max(value) AS hi
            FROM cluster_values
            GROUP BY cluster_coordinate
        ),
        binned AS (
            SELECT
                cluster_values.cluster_coordinate,
                stats.lo,
                stats.hi,
                cluster_values.outcome,
                CASE
                    WHEN stats.lo = stats.hi THEN 0
                    ELSE LEAST(%s - 1, floor(((cluster_values.value - stats.lo) / NULLIF(stats.hi - stats.lo, 0)) * %s)::int)
                END AS bin
            FROM cluster_values
            JOIN stats USING (cluster_coordinate)
        )
        SELECT
            cluster_coordinate AS coordinate,
            lo,
            hi,
            bin,
            count(*) AS count,
            count(*) FILTER (WHERE outcome = 'pass') AS pass_count,
            count(*) FILTER (WHERE outcome IS DISTINCT FROM 'pass') AS fail_count
        FROM binned
        GROUP BY cluster_coordinate, lo, hi, bin
    """
    return [
        {
            "score_family": EMOTION_CLUSTER_SCORE_FAMILY,
            "coordinate": str(row["coordinate"]),
            "lo": float(row["lo"]),
            "hi": float(row["hi"]),
            "bin": int(row["bin"]),
            "count": int(row["count"]),
            "pass_count": int(row["pass_count"]),
            "fail_count": int(row["fail_count"]),
        }
        for row in conn.execute(query, (_emotion_cluster_mapping_json(), run_id, n_bins, n_bins))
    ]


def _summary_emotion_cluster_tail_rows(conn: psycopg.Connection, run_id: str, *, n_tail: int = 10) -> list[dict[str, Any]]:
    query = f"""
        WITH cluster_members AS (
            SELECT *
            FROM jsonb_to_recordset(%s::jsonb) AS members(
                cluster_name text,
                cluster_coordinate text,
                member_concept text,
                member_coordinate text
            )
        ),
        cluster_values AS (
            SELECT
                cluster_members.cluster_name,
                cluster_members.cluster_coordinate,
                rows.example_key,
                rows.trace_id,
                rows.turn_index,
                avg(rows.score) AS value,
                max(rows.domain) AS domain,
                max(rows.task_id) AS task_id,
                max(rows.outcome) AS outcome,
                max(rows.reward) AS reward,
                max(rows.role) AS role,
                max(rows.summary::text) AS summary
            FROM {_score_table()} AS rows
            JOIN cluster_members ON cluster_members.member_coordinate = rows.coordinate
            WHERE rows.run_id = %s
                AND rows.score_family = 'emotion'
                AND rows.score IS NOT NULL
            GROUP BY
                cluster_members.cluster_name,
                cluster_members.cluster_coordinate,
                rows.example_key,
                rows.trace_id,
                rows.turn_index
        ),
        ranked AS (
            SELECT
                *,
                row_number() OVER (PARTITION BY cluster_coordinate ORDER BY value DESC NULLS LAST) AS positive_rank,
                row_number() OVER (PARTITION BY cluster_coordinate ORDER BY value ASC NULLS LAST) AS negative_rank
            FROM cluster_values
        )
        SELECT
            cluster_name,
            cluster_coordinate AS coordinate,
            trace_id,
            turn_index,
            value,
            domain,
            task_id,
            outcome,
            reward,
            role,
            summary,
            positive_rank,
            negative_rank
        FROM ranked
        WHERE positive_rank <= %s OR negative_rank <= %s
    """
    return [
        {
            "score_family": EMOTION_CLUSTER_SCORE_FAMILY,
            "coordinate": str(row["coordinate"]),
            "cluster": str(row["cluster_name"]),
            "trace_id": row.get("trace_id"),
            "turn_index": row.get("turn_index"),
            "value": float(row["value"]),
            "domain": row.get("domain"),
            "task_id": row.get("task_id"),
            "outcome": row.get("outcome"),
            "reward": row.get("reward"),
            "role": row.get("role"),
            "summary": row.get("summary"),
            "positive_rank": int(row["positive_rank"]),
            "negative_rank": int(row["negative_rank"]),
        }
        for row in conn.execute(query, (_emotion_cluster_mapping_json(), run_id, n_tail, n_tail))
    ]


def _summary_high_stakes_probe_stats(conn: psycopg.Connection, run_id: str) -> list[dict[str, Any]]:
    stats_query = f"""
        WITH valued AS (
            SELECT
                coordinate,
                prediction,
                CASE
                    WHEN probability IS NOT NULL AND positive_class = 'low-stakes' THEN 1.0 - probability
                    ELSE probability
                END AS value
            FROM {_score_table()}
            WHERE run_id = %s AND score_family = 'high_stakes'
        )
        SELECT
            coordinate,
            avg(value) AS mean_high_stakes_probability,
            avg(CASE WHEN value >= 0.5 THEN 1.0 ELSE 0.0 END) AS high_stakes_rate,
            count(*) AS rows
        FROM valued
        WHERE value IS NOT NULL AND coordinate IS NOT NULL
        GROUP BY coordinate
    """
    prediction_query = f"""
        SELECT coordinate, prediction, count(*) AS rows
        FROM {_score_table()}
        WHERE run_id = %s
            AND score_family = 'high_stakes'
            AND coordinate IS NOT NULL
            AND prediction IS NOT NULL
            AND prediction <> ''
        GROUP BY coordinate, prediction
    """
    predictions: dict[str, dict[str, int]] = {}
    for row in conn.execute(prediction_query, (run_id,)):
        predictions.setdefault(str(row["coordinate"]), {})[str(row["prediction"])] = int(row["rows"])

    stats = [
        {
            "coordinate": str(row["coordinate"]),
            "mean_high_stakes_probability": round(float(row["mean_high_stakes_probability"]), 6),
            "high_stakes_rate": round(float(row["high_stakes_rate"]), 6),
            "rows": int(row["rows"]),
            "predictions": predictions.get(str(row["coordinate"]), {}),
        }
        for row in conn.execute(stats_query, (run_id,))
    ]
    stats.sort(key=lambda row: float(row["mean_high_stakes_probability"]), reverse=True)
    return stats


def _summary_conversation_dynamics(conn: psycopg.Connection, run_id: str) -> list[dict[str, Any]]:
    query = f"""
        WITH max_turn AS (
            SELECT trace_id, max(turn_index) AS max_turn
            FROM {_score_table()}
            WHERE run_id = %s AND trace_id IS NOT NULL AND turn_index IS NOT NULL
            GROUP BY trace_id
        ),
        valued AS (
            SELECT
                rows.coordinate,
                CASE
                    WHEN rows.score_family = 'high_stakes' AND rows.probability IS NOT NULL AND rows.positive_class = 'low-stakes' THEN 1.0 - rows.probability
                    WHEN rows.score_family = 'high_stakes' THEN rows.probability
                    ELSE rows.score
                END AS value,
                CASE
                    WHEN rows.turn_index::float / GREATEST(max_turn.max_turn, 1) <= 0.33 THEN 'early'
                    WHEN rows.turn_index::float / GREATEST(max_turn.max_turn, 1) <= 0.67 THEN 'mid'
                    ELSE 'late'
                END AS segment
            FROM {_score_table()} AS rows
            JOIN max_turn ON max_turn.trace_id = rows.trace_id
            WHERE rows.run_id = %s
                AND rows.coordinate = ANY(%s)
                AND rows.turn_index IS NOT NULL
        )
        SELECT
            coordinate,
            avg(value) FILTER (WHERE segment = 'early') AS early,
            avg(value) FILTER (WHERE segment = 'mid') AS mid,
            avg(value) FILTER (WHERE segment = 'late') AS late,
            count(*) AS rows
        FROM valued
        WHERE value IS NOT NULL
        GROUP BY coordinate
        HAVING avg(value) FILTER (WHERE segment = 'early') IS NOT NULL
            AND avg(value) FILTER (WHERE segment = 'late') IS NOT NULL
    """
    dynamics: list[dict[str, Any]] = []
    for row in conn.execute(query, (run_id, run_id, list(IMPORTANT_DYNAMIC_COORDINATES))):
        early = float(row["early"])
        late = float(row["late"])
        dynamics.append(
            {
                "coordinate": str(row["coordinate"]),
                "early": round(early, 6),
                "mid": _round_or_none(row["mid"]),
                "late": round(late, 6),
                "delta": round(late - early, 6),
                "rows": int(row["rows"]),
            }
        )
    dynamics.sort(key=lambda row: abs(float(row["delta"])), reverse=True)
    return dynamics


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


def _emotion_cluster_stats_for_rows(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    by_member = {
        member["member_coordinate"]: member
        for member in _emotion_cluster_mapping_rows()
    }
    values_by_turn: dict[tuple[str, int | None, str | None], list[float]] = {}
    cluster_by_key: dict[tuple[str, int | None, str | None], Mapping[str, Any]] = {}
    for row in rows:
        member = by_member.get(str(row.get("coordinate") or ""))
        score = row.get("score")
        if not member or score is None:
            continue
        key = (str(member["cluster_coordinate"]), _optional_int(row.get("turn_index")), _optional_text(row.get("example_key")))
        values_by_turn.setdefault(key, []).append(float(score))
        cluster_by_key[key] = member

    cluster_values: dict[str, list[float]] = {}
    for key, values in values_by_turn.items():
        member = cluster_by_key[key]
        cluster_values.setdefault(str(member["cluster_coordinate"]), []).append(sum(values) / len(values))

    metadata = _emotion_cluster_metadata_by_coordinate()
    stats: list[dict[str, Any]] = []
    for coordinate, values in cluster_values.items():
        sorted_values = sorted(values)
        meta = metadata.get(coordinate, {})
        stats.append(
            {
                "coordinate": coordinate,
                "cluster": meta.get("cluster", coordinate),
                "mean": round(sum(sorted_values) / len(sorted_values), 6),
                "min": round(sorted_values[0], 6),
                "max": round(sorted_values[-1], 6),
                "rows": len(sorted_values),
                "members": meta.get("members", []),
                "member_coordinates": meta.get("member_coordinates", []),
                "member_count": meta.get("member_count", 0),
            }
        )
    stats.sort(key=lambda row: abs(float(row["mean"])), reverse=True)
    return stats


@lru_cache(maxsize=1)
def _emotion_cluster_mapping_json() -> str:
    return json.dumps(_emotion_cluster_mapping_rows(), separators=(",", ":"))


@lru_cache(maxsize=1)
def _emotion_cluster_mapping_rows() -> tuple[dict[str, str], ...]:
    rows: list[dict[str, str]] = []
    for cluster, members in _paper_emotion_clusters().items():
        cluster_coordinate = f"{EMOTION_CLUSTER_SCORE_FAMILY}__{_safe_coordinate_suffix(cluster)}"
        for member in members:
            rows.append(
                {
                    "cluster_name": cluster,
                    "cluster_coordinate": cluster_coordinate,
                    "member_concept": member,
                    "member_coordinate": f"emotion__{_safe_coordinate_suffix(member)}",
                }
            )
    return tuple(rows)


@lru_cache(maxsize=1)
def _emotion_cluster_metadata() -> list[dict[str, Any]]:
    by_coordinate = _emotion_cluster_metadata_by_coordinate()
    return [by_coordinate[coordinate] for coordinate in sorted(by_coordinate)]


@lru_cache(maxsize=1)
def _emotion_cluster_metadata_by_coordinate() -> dict[str, dict[str, Any]]:
    metadata: dict[str, dict[str, Any]] = {}
    for row in _emotion_cluster_mapping_rows():
        coordinate = row["cluster_coordinate"]
        bucket = metadata.setdefault(
            coordinate,
            {
                "cluster": row["cluster_name"],
                "coordinate": coordinate,
                "members": [],
                "member_coordinates": [],
                "member_count": 0,
                "reference": "Transformer Circuits emotions paper Table 12 clusters",
            },
        )
        bucket["members"].append(row["member_concept"])
        bucket["member_coordinates"].append(row["member_coordinate"])
        bucket["member_count"] += 1
    return metadata


@lru_cache(maxsize=1)
def _paper_emotion_clusters() -> dict[str, tuple[str, ...]]:
    try:
        from papers.voice.emotions.replication.validation import _PAPER_EMOTION_CLUSTERS
    except Exception:
        return {}
    return {
        str(cluster): tuple(str(member) for member in members)
        for cluster, members in _PAPER_EMOTION_CLUSTERS.items()
    }


def _safe_coordinate_suffix(value: str) -> str:
    return "_".join(str(value or "").lower().replace("-", " ").split())


def _optional_int(value: Any) -> int | None:
    return int(value) if value is not None else None


def _optional_text(value: Any) -> str | None:
    return str(value) if value is not None else None


def _module_score(module: str, trace_id: str, score: float | None, metric: str) -> dict[str, Any] | None:
    if score is None:
        return None
    return {
        "module": module,
        "trace_id": trace_id,
        "scorer_model": "xenon_tau2_neon_scores",
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
        bucket = buckets.setdefault(coordinate, {"coordinate": coordinate, "sum": 0.0, "n": 0, "min": None, "max": None})
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


def _score_run_id(provider: str | None = None) -> str:
    normalized = _normalized_score_provider(provider)
    if normalized == "hermes":
        return os.environ.get(HERMES_SCORE_RUN_ID_ENV) or HERMES_DEFAULT_RUN_ID
    return os.environ.get("BEHAVIOR_AUDIT_SCORE_RUN_ID") or DEFAULT_RUN_ID


def _score_table() -> str:
    if _CURRENT_PROVIDER.get() == "hermes":
        return _safe_identifier(os.environ.get(HERMES_SCORE_TABLE_ENV) or HERMES_SCORE_TABLE)
    return _safe_identifier(os.environ.get(SCORE_TABLE_ENV) or SCORE_TABLE)


def _score_summary_table() -> str:
    return _safe_identifier(os.environ.get(SCORE_SUMMARY_TABLE_ENV) or SCORE_SUMMARY_TABLE)


def _normalized_score_provider(provider: str | None = None) -> str:
    if provider is None:
        return _CURRENT_PROVIDER.get()
    normalized = str(provider).strip().lower().replace("_", "-")
    if normalized.startswith("hermes"):
        return "hermes"
    return "tau2"


def _safe_identifier(value: str) -> str:
    if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", value):
        raise ValueError(f"unsafe SQL identifier: {value!r}")
    return value


@lru_cache(maxsize=4)
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
    return [
        dict(row)
        for row in _supplemental_score_rows(run_id)
        if str(row.get("trace_id") or "") == str(trace_id)
    ]


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
    rows = [dict(row) for row in existing_rows if isinstance(row, Mapping)] if isinstance(existing_rows, Sequence) and not isinstance(existing_rows, (str, bytes)) else []
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
                "mean": _mean_float(values),
                "min": sorted_values[0],
                "max": sorted_values[-1],
                "q05": _quantile(sorted_values, 0.05),
                "q20": _quantile(sorted_values, 0.20),
                "q40": _quantile(sorted_values, 0.40),
                "q50": _quantile(sorted_values, 0.50),
                "q60": _quantile(sorted_values, 0.60),
                "q80": _quantile(sorted_values, 0.80),
                "q95": _quantile(sorted_values, 0.95),
                "pass_correlation": _pearson_float(
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
        early = _mean_float(segments["early"])
        late = _mean_float(segments["late"])
        dynamics.append(
            {
                "coordinate": coordinate,
                "early": round(early, 6),
                "mid": round(_mean_float(segments["mid"]), 6) if segments.get("mid") else None,
                "late": round(late, 6),
                "delta": round(late - early, 6),
                "rows": sum(len(values) for values in segments.values()),
            }
        )
    dynamics.sort(key=lambda row: abs(float(row["delta"])), reverse=True)
    return dynamics


def _mean_float(values: Sequence[float]) -> float:
    return sum(float(value) for value in values) / max(len(values), 1)


def _quantile(sorted_values: Sequence[float], q: float) -> float | None:
    if not sorted_values:
        return None
    if len(sorted_values) == 1:
        return float(sorted_values[0])
    position = (len(sorted_values) - 1) * q
    lower = int(position)
    upper = min(lower + 1, len(sorted_values) - 1)
    weight = position - lower
    return float(sorted_values[lower]) * (1 - weight) + float(sorted_values[upper]) * weight


def _pearson_float(xs: Sequence[float], ys: Sequence[float]) -> float | None:
    if len(xs) < 2 or len(xs) != len(ys):
        return None
    mean_x = _mean_float(xs)
    mean_y = _mean_float(ys)
    numerator = sum((float(x) - mean_x) * (float(y) - mean_y) for x, y in zip(xs, ys))
    denom_x = sum((float(x) - mean_x) ** 2 for x in xs)
    denom_y = sum((float(y) - mean_y) ** 2 for y in ys)
    if denom_x <= 0 or denom_y <= 0:
        return None
    return numerator / ((denom_x * denom_y) ** 0.5)


def _database_url() -> str | None:
    return configured_database_url(DB_ENV_VAR)


def _table_exists(conn: psycopg.Connection, table_name: str) -> bool:
    row = conn.execute("SELECT to_regclass(%s) AS table_name", (table_name,)).fetchone()
    return bool(row and row.get("table_name"))
