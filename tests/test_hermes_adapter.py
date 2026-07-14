"""Hermes adapter coverage: reading a real (fixture) state.db into AuditTraces."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from backend.adapters.hermes import state_db_loader
from backend.adapters.hermes.adapter import load_audit_traces_from_env
from backend.adapters.hermes.state_db import read_traces


def _build_state_db(path: Path) -> None:
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE sessions (
            id TEXT PRIMARY KEY,
            source TEXT,
            user_id TEXT,
            model TEXT,
            system_prompt TEXT,
            parent_session_id TEXT,
            started_at REAL,
            ended_at REAL,
            end_reason TEXT,
            title TEXT,
            archived INTEGER DEFAULT 0
        );
        CREATE TABLE messages (
            id INTEGER PRIMARY KEY,
            session_id TEXT,
            role TEXT,
            content TEXT,
            tool_call_id TEXT,
            tool_calls TEXT,
            tool_name TEXT,
            timestamp REAL,
            reasoning TEXT,
            reasoning_content TEXT,
            active INTEGER DEFAULT 1
        );
        """
    )
    conn.execute(
        "INSERT INTO sessions VALUES ('sess_1','cli','dev_1','model-x','be helpful',NULL,1.0,2.0,'completed','Fix bug',0)"
    )
    conn.execute(
        "INSERT INTO sessions VALUES ('sess_2','telegram',NULL,'model-x','be helpful',NULL,3.0,4.0,'completed',NULL,1)"
    )
    rows = [
        (1, "sess_1", "user", "My build fails.", None, None, None, 1.1, None, None, 1),
        (
            2,
            "sess_1",
            "assistant",
            "Let me check the log.",
            None,
            None,
            None,
            1.2,
            "user is stuck; read log first",
            None,
            1,
        ),
        (3, "sess_1", "assistant", "This row is inactive and must be skipped.", None, None, None, 1.3, None, None, 0),
        (
            4,
            "sess_1",
            "ai",
            "Fixed: missing import.",
            None,
            '[{"function": {"name": "apply_patch"}}]',
            None,
            1.4,
            None,
            None,
            1,
        ),
        (5, "sess_2", "user", "archived session", None, None, None, 3.1, None, None, 1),
    ]
    conn.executemany("INSERT INTO messages VALUES (?,?,?,?,?,?,?,?,?,?,?)", rows)
    conn.commit()
    conn.close()


@pytest.fixture()
def state_db(tmp_path, monkeypatch) -> Path:
    db_path = tmp_path / "state.db"
    _build_state_db(db_path)
    monkeypatch.setenv("PERSONA_AUDIT_HERMES_STATE_DB", str(db_path))
    monkeypatch.delenv("HERMES_SIDECAR_STATE_DB", raising=False)
    monkeypatch.delenv("PERSONA_AUDIT_HERMES_INCLUDE_ARCHIVED", raising=False)
    state_db_loader.load_traces_from_env.cache_clear()
    yield db_path
    state_db_loader.load_traces_from_env.cache_clear()


def test_read_traces_normalizes_roles_reasoning_and_activity(state_db) -> None:
    traces = read_traces(state_db)
    assert [trace.trace_id for trace in traces] == ["sess_1"], "archived sessions are excluded by default"
    trace = traces[0]
    assert [turn.role for turn in trace.turns] == ["user", "assistant", "assistant"], "inactive rows are skipped"
    assert trace.turns[1].reasoning == "user is stuck; read log first"
    assert trace.turns[2].tool_name == "apply_patch", "tool name is pulled from the tool_calls JSON"
    assert trace.title == "Fix bug"


def test_read_traces_can_include_archived(state_db) -> None:
    traces = read_traces(state_db, include_archived=True)
    assert {trace.trace_id for trace in traces} == {"sess_1", "sess_2"}


def test_load_audit_traces_shapes_the_product_trace(state_db) -> None:
    traces, provider_id, source = load_audit_traces_from_env()
    assert provider_id == "hermes_local"
    assert str(state_db) in source
    trace = traces[0]
    assert trace.domain == "cli"
    assert trace.user_id == "dev_1"
    assert trace.labels["provider"] == "hermes"
    assert trace.labels["has_reasoning"] is True
    assert trace.outcome == "completed"


def test_missing_db_falls_back_to_smoke_fixture(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("PERSONA_AUDIT_HERMES_STATE_DB", str(tmp_path / "nope.db"))
    monkeypatch.delenv("HERMES_SIDECAR_STATE_DB", raising=False)
    state_db_loader.load_traces_from_env.cache_clear()
    try:
        traces, provider_id, source = load_audit_traces_from_env()
        assert provider_id == "hermes_smoke"
        assert source == "Hermes demo fixture"
        assert traces
    finally:
        state_db_loader.load_traces_from_env.cache_clear()
