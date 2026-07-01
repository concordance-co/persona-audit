"""Current product trace source.

The product-level report code consumes normalized ``AuditTrace`` objects. This
module is the only place that decides where those traces come from today.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Mapping, Sequence

import psycopg
from psycopg import sql
from psycopg.rows import dict_row

from backend.adapters.hermes.adapter import load_audit_traces_from_env as load_hermes_traces_from_env
from backend.api.models import AuditTrace, AuditTurn
from backend.api.neon_scores import _safe_identifier
from backend.api.provider import HERMES_PROVIDER, resolve_provider
from backend.api.tau2_loader import configured_provider_id, load_traces_from_env
from backend.paths import DATABASE_URL_ENV, LEGACY_DATABASE_URL_ENV, configured_database_url, load_dotenv


DB_ENV_VAR = DATABASE_URL_ENV
LEGACY_DB_ENV_VAR = LEGACY_DATABASE_URL_ENV
TRACE_SOURCE_ENV = "BEHAVIOR_AUDIT_TRACE_SOURCE"
TRACE_TABLE_ENV = "BEHAVIOR_AUDIT_TRACE_TABLE"
TURN_TABLE_ENV = "BEHAVIOR_AUDIT_TURN_TABLE"
TRACE_TABLE = "behavior_audit_traces"
TURN_TABLE = "behavior_audit_turns"


def load_product_traces(provider: str | None = None, *, prefer_neon: bool = True) -> tuple[list[AuditTrace], str, str]:
    selected = resolve_provider(provider)
    if prefer_neon and _trace_source_mode() != "local":
        neon_traces = _load_neon_product_traces(selected)
        if neon_traces is not None:
            return neon_traces
    if selected == HERMES_PROVIDER:
        return load_hermes_traces_from_env()
    traces, source, provider_id = load_traces_from_env()
    return traces, provider_id, source


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


def _load_neon_product_traces(selected_provider: str) -> tuple[list[AuditTrace], str, str] | None:
    database_url = _database_url()
    if not database_url:
        return None
    trace_table = _trace_table()
    turn_table = _turn_table()
    try:
        with psycopg.connect(database_url, row_factory=dict_row) as conn:
            provider_ids = _neon_provider_ids(conn, selected_provider, trace_table)
            if not provider_ids:
                return None
            provider_id = _preferred_neon_provider_id(selected_provider, provider_ids)
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
    except psycopg.Error:
        return None
    traces = traces_from_neon_rows(trace_rows, turn_rows)
    if not traces:
        return None
    source = f"Postgres {trace_table}/{turn_table}"
    return traces, provider_id, source


def _neon_provider_ids(conn: psycopg.Connection, selected_provider: str, trace_table: str) -> list[str]:
    if not _table_exists(conn, trace_table):
        return []
    if selected_provider == HERMES_PROVIDER:
        provider_filter = sql.SQL("provider_id LIKE 'hermes%'")
    else:
        provider_filter = sql.SQL("provider_id NOT LIKE 'hermes%'")
    query = sql.SQL(
        """
        SELECT provider_id, count(*) AS rows
        FROM {trace_table}
        WHERE {provider_filter}
        GROUP BY provider_id
        ORDER BY rows DESC, provider_id
        """
    ).format(trace_table=sql.Identifier(trace_table), provider_filter=provider_filter)
    return [str(row["provider_id"]) for row in conn.execute(query)]


def _preferred_neon_provider_id(selected_provider: str, provider_ids: Sequence[str]) -> str:
    if selected_provider == HERMES_PROVIDER:
        preferred = "hermes_local"
    else:
        preferred = configured_provider_id()
    return preferred if preferred in provider_ids else str(provider_ids[0])


def _table_exists(conn: psycopg.Connection, table_name: str) -> bool:
    row = conn.execute("SELECT to_regclass(%s) AS table_name", (table_name,)).fetchone()
    return bool(row and row.get("table_name"))


def _trace_table() -> str:
    return _safe_identifier(os.environ.get(TRACE_TABLE_ENV) or TRACE_TABLE)


def _turn_table() -> str:
    return _safe_identifier(os.environ.get(TURN_TABLE_ENV) or TURN_TABLE)


def _database_url() -> str | None:
    return configured_database_url(DB_ENV_VAR)


def _trace_source_mode() -> str:
    load_dotenv()
    return os.environ.get(TRACE_SOURCE_ENV, "").strip().lower()


def _turn_sort_key(row: Mapping[str, Any]) -> tuple[int, str]:
    index = row.get("turn_index")
    return (int(index) if index is not None else 0, str(row.get("turn_id") or ""))


def _float_or_none(value: Any) -> float | None:
    return None if value is None else float(value)


def _mapping_or_empty(value: Any) -> Mapping[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}
