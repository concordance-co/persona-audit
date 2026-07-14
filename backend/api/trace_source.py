"""Product trace loading: registry-driven dispatch over local and Postgres sources.

Resolution order for a provider (see ``backend.api.registry``):

1. ``local_only`` providers (bundled datasets) always use their local loader.
2. Otherwise, if a database is configured and ``PERSONA_AUDIT_TRACE_SOURCE``
   is not ``local``, rows are read from the trace/turn tables, claimed per
   provider via ``ProviderSpec.db_provider_id_prefix``.
3. Fall back to the provider's local loader (bundled snapshots or smoke data).

No provider-specific branches belong in this module; that knowledge lives on
each ``ProviderSpec``.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from typing import Any

import psycopg
from psycopg import sql
from psycopg.rows import dict_row

from backend.api.db import configured_database_url, safe_identifier, table_exists
from backend.api.models import AuditTrace, AuditTurn
from backend.api.registry import (
    ProviderSpec,
    TraceLoadResult,
    get_provider,
    provider_descriptor,
    resolve_provider,
)
from backend.paths import env_value, load_dotenv

logger = logging.getLogger(__name__)

TRACE_SOURCE_ENV = "PERSONA_AUDIT_TRACE_SOURCE"
TRACE_TABLE_ENV = "PERSONA_AUDIT_TRACE_TABLE"
TURN_TABLE_ENV = "PERSONA_AUDIT_TURN_TABLE"
TRACE_TABLE = "persona_audit_traces"
TURN_TABLE = "persona_audit_turns"


def load_product_traces(provider: str | None = None, *, prefer_neon: bool = True) -> TraceLoadResult:
    spec = get_provider(provider)
    if spec.local_only:
        return spec.load_traces()
    if prefer_neon and _trace_source_mode() != "local":
        neon_traces = _load_neon_product_traces(spec)
        if neon_traces is not None:
            return neon_traces
    return spec.load_traces()


TRACK_PREFERRED_ORDER = ("sol", "marrow", "control")


def track_group_map(provider: str | None = None) -> tuple[list[str], dict[str, str]] | None:
    """Ordered track names plus trace_id -> track, for track-comparison providers.

    Returns None for providers without the track-comparison feature, so callers
    can gate per-track breakdowns on a single lookup. Tracks live on the shaped
    trace's ``domain`` (see providers/persona_demo.py:_shape_trace).
    """

    selected = resolve_provider(provider)
    features = provider_descriptor(selected).get("features") or {}
    if not features.get("show_track_comparison"):
        return None
    traces, _, _ = load_product_traces(selected)
    groups = {trace.trace_id: str(trace.domain or "unknown") for trace in traces}
    names = set(groups.values())
    ordered = [track for track in TRACK_PREFERRED_ORDER if track in names]
    ordered.extend(track for track in sorted(names) if track not in ordered)
    return ordered, groups


def traces_from_neon_rows(
    trace_rows: Sequence[Mapping[str, Any]],
    turn_rows: Sequence[Mapping[str, Any]],
) -> list[AuditTrace]:
    turns_by_trace: dict[str, list[Mapping[str, Any]]] = {}
    for row in turn_rows:
        turns_by_trace.setdefault(str(row.get("trace_id") or ""), []).append(row)

    traces: list[AuditTrace] = []
    for row in trace_rows:
        trace_id = str(row["trace_id"])
        turns = tuple(
            AuditTurn(
                turn_id=str(turn.get("turn_id") or f"turn_{index:03d}"),
                role=str(turn.get("role") or ""),
                content=str(turn.get("content") or ""),
                index=int(turn.get("turn_index") if turn.get("turn_index") is not None else index),
                tool_name=turn.get("tool_name"),
            )
            for index, turn in enumerate(sorted(turns_by_trace.get(trace_id, []), key=_turn_sort_key))
        )
        traces.append(
            AuditTrace(
                trace_id=trace_id,
                session_id=str(row.get("session_id") or trace_id),
                user_id=str(row.get("user_id") or ""),
                domain=str(row.get("domain") or ""),
                task_id=str(row.get("task_id") or ""),
                outcome=str(row.get("outcome") or ""),
                reward=_float_or_none(row.get("reward")),
                source_model=str(row.get("source_model") or ""),
                user_model=str(row.get("user_model") or ""),
                turns=turns,
                labels=_mapping_or_empty(row.get("labels")),
                metadata=_mapping_or_empty(row.get("metadata")),
            )
        )
    return traces


def _load_neon_product_traces(spec: ProviderSpec) -> TraceLoadResult | None:
    database_url = _database_url()
    if not database_url:
        return None
    trace_table = _trace_table()
    turn_table = _turn_table()
    try:
        with psycopg.connect(database_url, row_factory=dict_row) as conn:
            provider_ids = _neon_provider_ids(conn, spec, trace_table)
            if not provider_ids:
                return None
            provider_id = _preferred_neon_provider_id(spec, provider_ids)
            trace_rows = [
                dict(row)
                for row in conn.execute(
                    sql.SQL(
                        """
                        SELECT
                            provider_id,
                            trace_id,
                            session_id,
                            user_id,
                            domain,
                            task_id,
                            outcome,
                            reward,
                            source_model,
                            user_model,
                            labels,
                            metadata,
                            source
                        FROM {trace_table}
                        WHERE provider_id = %s
                        ORDER BY trace_id
                        """
                    ).format(trace_table=sql.Identifier(trace_table)),
                    (provider_id,),
                )
            ]
            if not trace_rows:
                return None
            turn_rows = [
                dict(row)
                for row in conn.execute(
                    sql.SQL(
                        """
                        SELECT
                            provider_id,
                            trace_id,
                            turn_id,
                            turn_index,
                            role,
                            content,
                            tool_name
                        FROM {turn_table}
                        WHERE provider_id = %s
                        ORDER BY trace_id, turn_index
                        """
                    ).format(turn_table=sql.Identifier(turn_table)),
                    (provider_id,),
                )
            ]
    except psycopg.Error as exc:
        logger.warning("trace DB query failed; falling back to the local loader: %s", exc)
        return None
    traces = traces_from_neon_rows(trace_rows, turn_rows)
    if not traces:
        return None
    source = f"Postgres {trace_table}/{turn_table}"
    return TraceLoadResult(traces=traces, provider_id=provider_id, source=source)


def _provider_id_filter(spec: ProviderSpec) -> sql.Composable:
    """Which provider_id rows in a shared trace table belong to this provider.

    Providers with a ``db_provider_id_prefix`` claim rows by prefix; providers
    without one get everything not claimed by another provider's prefix.
    """

    from backend.api.providers import REGISTRY

    if spec.db_provider_id_prefix:
        return sql.SQL("provider_id LIKE {}").format(sql.Literal(spec.db_provider_id_prefix + "%"))
    other_prefixes = [
        other.db_provider_id_prefix
        for other in REGISTRY.values()
        if other.key != spec.key and other.db_provider_id_prefix
    ]
    if not other_prefixes:
        return sql.SQL("TRUE")
    return sql.SQL(" AND ").join(
        sql.SQL("provider_id NOT LIKE {}").format(sql.Literal(prefix + "%")) for prefix in other_prefixes
    )


def _neon_provider_ids(conn: psycopg.Connection, spec: ProviderSpec, trace_table: str) -> list[str]:
    if not table_exists(conn, trace_table):
        return []
    query = sql.SQL(
        """
        SELECT provider_id, count(*) AS rows
        FROM {trace_table}
        WHERE {provider_filter}
        GROUP BY provider_id
        ORDER BY rows DESC, provider_id
        """
    ).format(trace_table=sql.Identifier(trace_table), provider_filter=_provider_id_filter(spec))
    return [str(row["provider_id"]) for row in conn.execute(query)]


def _preferred_neon_provider_id(spec: ProviderSpec, provider_ids: Sequence[str]) -> str:
    preferred = spec.preferred_db_provider_id() if spec.preferred_db_provider_id else None
    return preferred if preferred in provider_ids else str(provider_ids[0])


def _trace_table() -> str:
    return safe_identifier(env_value(TRACE_TABLE_ENV) or TRACE_TABLE)


def _turn_table() -> str:
    return safe_identifier(env_value(TURN_TABLE_ENV) or TURN_TABLE)


def _database_url() -> str | None:
    return configured_database_url()


def _trace_source_mode() -> str:
    load_dotenv()
    return env_value(TRACE_SOURCE_ENV, "").strip().lower()


def _turn_sort_key(row: Mapping[str, Any]) -> tuple[int, str]:
    index = row.get("turn_index")
    return (int(index) if index is not None else 0, str(row.get("turn_id") or ""))


def _float_or_none(value: Any) -> float | None:
    return None if value is None else float(value)


def _mapping_or_empty(value: Any) -> Mapping[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}
