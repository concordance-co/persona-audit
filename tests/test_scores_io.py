"""scores_io write path (fake connection) and SQL<->offline summary parity."""

from __future__ import annotations

import gzip
import json

from psycopg import sql

from backend.api.cache import clear_all
from backend.api.scores import offline, score_inventory, score_rows_for_trace
from backend.scores_io import (
    SCORE_COLUMNS,
    build_local_score_cache_payload,
    ensure_tables,
    local_score_cache_path,
    replace_run,
    write_local_score_cache,
)


class FakeCopy:
    def __init__(self) -> None:
        self.rows: list[tuple] = []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def write_row(self, row) -> None:
        self.rows.append(tuple(row))


class FakeCursor:
    def __init__(self, conn) -> None:
        self.conn = conn

    def copy(self, statement):
        self.conn.copy_statements.append(statement.as_string())
        copy = FakeCopy()
        self.conn.copies.append(copy)
        return copy


class FakeConnection:
    """Records executed SQL text + params instead of talking to Postgres."""

    def __init__(self) -> None:
        self.statements: list[tuple[str, tuple | dict | None]] = []
        self.copy_statements: list[str] = []
        self.copies: list[FakeCopy] = []

    def execute(self, statement, params=None):
        text = statement.as_string() if isinstance(statement, sql.Composable) else str(statement)
        self.statements.append((" ".join(text.split()), params))
        return self

    def cursor(self):
        return FakeCursor(self)


def test_ensure_tables_creates_run_score_tables_and_indexes() -> None:
    conn = FakeConnection()

    ensure_tables(conn, run_table="persona_audit_tau2_score_runs", score_table="persona_audit_tau2_score_rows")

    texts = [text for text, _ in conn.statements]
    assert any('CREATE TABLE IF NOT EXISTS "persona_audit_tau2_score_runs"' in text for text in texts)
    assert any('CREATE TABLE IF NOT EXISTS "persona_audit_tau2_score_rows"' in text for text in texts)
    assert sum("CREATE INDEX IF NOT EXISTS" in text for text in texts) == 3
    score_table_ddl = next(
        text for text in texts if '"persona_audit_tau2_score_rows"' in text and "CREATE TABLE" in text
    )
    for column in SCORE_COLUMNS:
        assert column in score_table_ddl


def test_replace_run_deletes_then_inserts_and_copies_rows() -> None:
    conn = FakeConnection()
    run_row = {
        "run_id": "wr_test",
        "workflow_name": "persona_audit_tau2_scoring_v1",
        "provider_id": "tau2_public_airline",
        "source": "test",
        "artifact_volume": "persona-audit-data",
        "artifact_root": "/data/artifacts/persona_audit_tau2_scoring_v1",
        "capture_artifact_id": "capture_1",
        "projection_artifact_id": "projection_1",
        "emotion_artifact_id": "emotion_1",
        "high_stakes_artifact_ids": [],
        "trace_count": 1,
        "record_count": 1,
        "score_row_count": 1,
        "metadata": {"score_family_counts": {"assistant_axis": 1}},
    }
    score_row = {column: None for column in SCORE_COLUMNS}
    score_row.update(
        {
            "run_id": "wr_test",
            "artifact_id": "projection_1",
            "score_family": "assistant_axis",
            "coordinate": "assistant_axis_trait__calm",
            "example_key": "ex_1",
            "trace_id": "trace_1",
            "metric": "score",
            "score": 0.5,
            "row_payload": {"score": 0.5},
        }
    )

    replace_run(
        conn,
        run_table="persona_audit_tau2_score_runs",
        score_table="persona_audit_tau2_score_rows",
        run_row=run_row,
        score_rows=[score_row],
    )

    texts = [text for text, _ in conn.statements]
    assert any(text.startswith('DELETE FROM "persona_audit_tau2_score_runs"') for text in texts)
    assert any(text.startswith('INSERT INTO "persona_audit_tau2_score_runs"') for text in texts)
    assert len(conn.copies) == 1
    copied = conn.copies[0].rows
    assert len(copied) == 1
    assert len(copied[0]) == len(SCORE_COLUMNS)
    assert copied[0][SCORE_COLUMNS.index("coordinate")] == "assistant_axis_trait__calm"


def test_local_score_cache_round_trips_through_offline_serving(tmp_path, monkeypatch) -> None:
    run_row = {
        "run_id": "wr_local_test",
        "workflow_name": "persona_audit_local_scoring_v1",
        "provider_id": "local",
        "source": "local fixture",
        "trace_count": 1,
        "record_count": 1,
        "metadata": {"score_family_counts": {"assistant_axis": 1}},
    }
    score_row = {
        "run_id": "wr_local_test",
        "artifact_id": "projection_1",
        "score_family": "assistant_axis",
        "coordinate": "assistant_axis_trait__calm",
        "example_key": "trace_1__turn_1",
        "trace_id": "trace_1",
        "turn_index": 1,
        "provider_id": "local",
        "score": 0.5,
        "row_payload": {"score": 0.5},
    }
    payload = build_local_score_cache_payload(run_row=run_row, score_rows=[score_row])

    path = write_local_score_cache(payload, tmp_path)

    assert path == tmp_path / "wr_local_test_assistant_trait_scores.json.gz"
    assert json.loads(gzip.decompress(path.read_bytes()))["rows"] == [score_row]
    monkeypatch.setenv("PERSONA_AUDIT_SCORE_CACHE_DIR", str(tmp_path))
    monkeypatch.setenv("PERSONA_AUDIT_LOCAL_SCORE_RUN_ID", "wr_local_test")
    for name in ("PERSONA_AUDIT_DATABASE_URL", "BEHAVIOR_AUDIT_DATABASE_URL", "XENON_NEON_DATABASE_URL"):
        monkeypatch.setenv(name, "")
    offline._supplemental_score_rows.cache_clear()
    assert offline._supplemental_score_rows("wr_local_test") == (score_row,)
    clear_all()
    assert score_inventory("local")["available"] is True
    assert score_rows_for_trace("trace_1", provider="local") == [score_row]
    clear_all()


def test_local_score_cache_path_rejects_path_traversal(tmp_path) -> None:
    for run_id in ("", "../outside", "nested/run"):
        try:
            local_score_cache_path(tmp_path, run_id)
        except ValueError:
            continue
        raise AssertionError(f"unsafe run id was accepted: {run_id!r}")


# --- SQL <-> offline parity -------------------------------------------------
#
# backend/api/scores/sql_summaries.py and backend/api/scores/offline.py compute
# the same summary fragments (one in SQL, one in Python). These constants pin
# the shared row shapes; if either twin changes shape, update both and these.

TAIL_STAT_KEYS = {
    "score_family",
    "coordinate",
    "rows",
    "mean",
    "min",
    "max",
    "q05",
    "q20",
    "q40",
    "q50",
    "q60",
    "q80",
    "q95",
    "pass_correlation",
    "outcome_rows",
}

TAIL_HISTOGRAM_KEYS = {"score_family", "coordinate", "lo", "hi", "bin", "count", "pass_count", "fail_count"}

TAIL_ROW_KEYS = {
    "score_family",
    "coordinate",
    "trace_id",
    "turn_index",
    "value",
    "domain",
    "task_id",
    "outcome",
    "reward",
    "role",
    "summary",
    "positive_rank",
    "negative_rank",
}

DYNAMICS_KEYS = {"coordinate", "early", "mid", "late", "delta", "rows"}


def _synthetic_rows() -> list[dict]:
    rows = []
    coordinate = next(iter(offline.IMPORTANT_DYNAMIC_COORDINATES))
    for trace in range(3):
        for turn in range(4):
            rows.append(
                {
                    "score_family": "assistant_axis",
                    "coordinate": coordinate,
                    "example_key": f"t{trace}_u{turn}",
                    "trace_id": f"trace_{trace}",
                    "turn_index": turn,
                    "score": 0.1 * turn + 0.05 * trace,
                    "outcome": "pass" if trace % 2 == 0 else "fail",
                    "domain": "demo",
                    "task_id": f"task_{trace}",
                    "reward": None,
                    "role": "assistant",
                    "summary": None,
                }
            )
    return rows


def test_offline_aggregations_emit_the_shared_summary_shapes() -> None:
    rows = _synthetic_rows()

    stats = offline._supplemental_tail_stats(rows)
    assert stats and all(set(stat) == TAIL_STAT_KEYS for stat in stats)
    assert all(stat["rows"] == 12 for stat in stats)

    histograms = offline._supplemental_tail_histograms(rows)
    assert histograms and all(set(item) == TAIL_HISTOGRAM_KEYS for item in histograms)
    assert sum(item["count"] for item in histograms) == 12
    assert all(item["count"] == item["pass_count"] + item["fail_count"] for item in histograms)

    tail_rows = offline._supplemental_tail_rows(rows)
    assert tail_rows and all(set(item) == TAIL_ROW_KEYS for item in tail_rows)

    dynamics = offline._supplemental_conversation_dynamics(rows)
    assert dynamics and all(set(item) == DYNAMICS_KEYS for item in dynamics)
    late_minus_early = dynamics[0]["late"] - dynamics[0]["early"]
    assert abs(dynamics[0]["delta"] - round(late_minus_early, 6)) < 1e-9
