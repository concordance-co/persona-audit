"""SQL builders for the materialized score summary (Postgres path).

SQL twin of backend.api.scores.offline: each ``_summary_X`` here has an
offline ``_supplemental_X`` counterpart computing the same summary shape from
bundled JSON rows. Keep their output shapes identical (tested in
tests/test_score_access.py).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import psycopg

from backend.api.db import table_exists as _table_exists
from backend.api.score_cache import SCORE_SUMMARY_CACHE_VERSION
from backend.api.scores.emotion_clusters import (
    EMOTION_CLUSTER_SCORE_FAMILY,
    NEGATIVE_AFFECT_COORDINATES,
    _emotion_cluster_mapping_json,
    _emotion_cluster_metadata,
    _emotion_cluster_metadata_by_coordinate,
)
from backend.api.scores.provider_context import current_score_table as _score_table
from backend.api.scores.provider_context import score_summary_table as _score_summary_table
from backend.api.scores.shaping import (
    IMPORTANT_DYNAMIC_COORDINATES,
    _coordinate_bands_from_summary,
    _coordinate_stats_from_summary,
    _float_or_none,
    _module_score,
    _projection_tail_thresholds_from_summary,
    _round_or_none,
    _tail_explorer_from_summary,
)


def _build_score_summary(conn: psycopg.Connection, run_id: str) -> dict[str, Any]:
    tail_stats = _summary_tail_stats(conn, run_id)
    return {
        "kind": "persona_audit_score_summary",
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
    if candidate.get("kind") != "persona_audit_score_summary":
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
                _module_score(
                    "sycophancy", trace_id, _float_or_none(row["sycophancy"]), "assistant_axis_trait__sycophantic"
                ),
                _module_score("high_stakes", trace_id, high_stakes, "adapted_probe_high_stakes_rate"),
                _module_score(
                    "emotion_posture",
                    trace_id,
                    _float_or_none(row["negative_affect"]),
                    "negative_affect_emotion_projection",
                ),
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


def _summary_emotion_cluster_histograms(
    conn: psycopg.Connection, run_id: str, *, n_bins: int = 18
) -> list[dict[str, Any]]:
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


def _summary_emotion_cluster_tail_rows(
    conn: psycopg.Connection, run_id: str, *, n_tail: int = 10
) -> list[dict[str, Any]]:
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
