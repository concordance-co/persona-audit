"""Read-only access to a Hermes ``state.db`` SQLite file.

This is the only module that touches Hermes's on-disk schema. It opens the
database in read-only mode (``mode=ro``) and never writes. The schema it reads
(``sessions`` and ``messages``) is Hermes-internal and has no stability
contract, so all column access is defensive: missing columns degrade to
``None`` rather than raising.

Schema reference (hermes-agent/hermes_state.py):
- ``sessions``: id, source, user_id, model, system_prompt, parent_session_id,
  started_at, ended_at, end_reason, title, archived, ...
- ``messages``: id, session_id, role, content, tool_call_id, tool_calls,
  tool_name, timestamp, reasoning, reasoning_content, ..., active
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from contextlib import closing
from pathlib import Path
from typing import Any

from backend.adapters.hermes.models import HermesTrace, HermesTurn
from backend.paths import env_value


def default_state_db_path() -> Path:
    """The Hermes database location.

    Defaults to ``~/.hermes/state.db`` but honors ``PERSONA_AUDIT_HERMES_STATE_DB``
    and the legacy ``HERMES_SIDECAR_STATE_DB`` so
    demos and tests can point at a synthetic database without touching a real
    ``~/.hermes`` directory.
    """

    override = (env_value("PERSONA_AUDIT_HERMES_STATE_DB") or env_value("HERMES_SIDECAR_STATE_DB") or "").strip()
    if override:
        return Path(override).expanduser()
    return Path.home() / ".hermes" / "state.db"


def connect_readonly(path: str | Path) -> sqlite3.Connection:
    """Open ``path`` read-only. Raises ``FileNotFoundError`` if it is missing.

    Opened with ``mode=ro`` (not ``immutable=1``): Hermes uses WAL journaling,
    so recent sessions live in the ``-wal`` sidecar until a checkpoint folds
    them into the main file. ``immutable=1`` would tell SQLite to ignore the
    WAL and miss that data, so we use plain read-only and let SQLite read the
    WAL via the existing ``-shm`` index.
    """

    resolved = Path(path).expanduser().resolve()
    if not resolved.exists():
        raise FileNotFoundError(f"Hermes state.db not found: {resolved}")
    conn = sqlite3.connect(f"file:{resolved}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _column_names(conn: sqlite3.Connection, table: str) -> set[str]:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return {str(row["name"]) for row in rows}


def _get(row: sqlite3.Row, key: str, default: Any = None) -> Any:
    return row[key] if key in row.keys() else default


def iter_traces(
    path: str | Path,
    *,
    include_archived: bool = False,
) -> Iterator[HermesTrace]:
    """Yield one :class:`HermesTrace` per (non-archived) session in ``path``."""

    with closing(connect_readonly(path)) as conn:
        session_cols = _column_names(conn, "sessions")
        has_archived = "archived" in session_cols
        where = "WHERE archived = 0" if (has_archived and not include_archived) else ""
        order = "ORDER BY started_at" if "started_at" in session_cols else "ORDER BY id"
        sessions = conn.execute(f"SELECT * FROM sessions {where} {order}").fetchall()
        for session in sessions:
            messages = conn.execute(
                "SELECT * FROM messages WHERE session_id = ? AND active = 1 ORDER BY id",
                (session["id"],),
            ).fetchall()
            yield _trace_from_rows(session, messages)


def read_traces(
    path: str | Path,
    *,
    include_archived: bool = False,
    limit: int = 0,
    require_turns: bool = True,
) -> list[HermesTrace]:
    """Read all sessions from ``path`` as normalized traces.

    ``require_turns`` drops sessions with no usable turns. ``limit`` caps the
    number of returned traces (0 = unlimited).
    """

    traces: list[HermesTrace] = []
    for trace in iter_traces(path, include_archived=include_archived):
        if require_turns and not trace.turns:
            continue
        traces.append(trace)
        if limit and len(traces) >= limit:
            break
    return traces


def _trace_from_rows(session: sqlite3.Row, messages: list[sqlite3.Row]) -> HermesTrace:
    session_id = str(session["id"])
    turns = tuple(_turn_from_row(row, index) for index, row in enumerate(messages))
    return HermesTrace(
        trace_id=session_id,
        session_id=session_id,
        user_id=str(_get(session, "user_id") or f"{_get(session, 'source') or 'unknown'}_anon"),
        source=str(_get(session, "source") or "unknown"),
        model=str(_get(session, "model") or "unknown"),
        system_prompt=str(_get(session, "system_prompt") or ""),
        turns=turns,
        started_at=_as_float(_get(session, "started_at")),
        ended_at=_as_float(_get(session, "ended_at")),
        end_reason=_opt_str(_get(session, "end_reason")),
        parent_session_id=_opt_str(_get(session, "parent_session_id")),
        title=_opt_str(_get(session, "title")),
        labels={
            "source": _get(session, "source"),
            "model": _get(session, "model"),
            "end_reason": _get(session, "end_reason"),
        },
        metadata={
            "source": "hermes_state_db",
            "user_id": _get(session, "user_id"),
            "started_at": _get(session, "started_at"),
            "message_count": _get(session, "message_count"),
            "tool_call_count": _get(session, "tool_call_count"),
            "input_tokens": _get(session, "input_tokens"),
            "output_tokens": _get(session, "output_tokens"),
        },
    )


def _turn_from_row(row: sqlite3.Row, index: int) -> HermesTurn:
    role = _normalize_role(str(_get(row, "role") or "unknown"))
    content = str(_get(row, "content") or "")
    tool_name = _opt_str(_get(row, "tool_name"))
    if tool_name is None and role == "assistant":
        tool_name = _first_tool_name(_get(row, "tool_calls"))
    reasoning = _opt_str(_get(row, "reasoning")) or _opt_str(_get(row, "reasoning_content"))
    return HermesTurn(
        turn_id=f"turn_{index:04d}",
        role=role,
        content=content,
        index=index,
        tool_name=tool_name,
        tool_call_id=_opt_str(_get(row, "tool_call_id")),
        reasoning=reasoning,
        timestamp=_as_float(_get(row, "timestamp")),
    )


def _first_tool_name(raw: Any) -> str | None:
    """Pull a tool name out of the ``tool_calls`` JSON column, if present."""

    if not raw:
        return None
    try:
        calls = json.loads(raw) if isinstance(raw, str) else raw
    except (json.JSONDecodeError, TypeError):
        return None
    if isinstance(calls, list):
        for call in calls:
            if not isinstance(call, dict):
                continue
            name = call.get("name")
            function = call.get("function")
            if not name and isinstance(function, dict):
                name = function.get("name")
            if name:
                return str(name)
    return None


def _normalize_role(role: str) -> str:
    cleaned = role.strip().lower()
    aliases = {"ai": "assistant", "model": "assistant", "function": "tool"}
    return aliases.get(cleaned, cleaned or "unknown")


def _opt_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text if text else None


def _as_float(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None
