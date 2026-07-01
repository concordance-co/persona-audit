from __future__ import annotations

"""Upload local Persona Audit data artifacts into Neon tables.

This covers the local product data that is useful to query directly:

- normalized traces and turns for public adapters
- supplemental score rows already shaped like the canonical score-row table
- derived score-summary JSON caches as materialized summaries
"""

import argparse
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

import psycopg
from psycopg import sql
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from backend.api.models import AuditTrace
from backend.api.neon_scores import (
    SCORE_TABLE,
    _safe_identifier,
)
from backend.api.trace_source import load_product_traces
from backend.scripts.upload_tau2_scores_to_neon import (
    DB_ENV_VAR,
    RUN_TABLE as TAU2_RUN_TABLE,
    SCORE_COLUMNS,
    _ensure_tables,
    _copy_value,
)
from backend.paths import DATA_ROOT, configured_database_url, load_dotenv


TRACE_TABLE = "behavior_audit_traces"
TURN_TABLE = "behavior_audit_turns"
SUMMARY_TABLE = "behavior_audit_score_summaries"
SUPPLEMENTAL_SCORE_DIR = DATA_ROOT / "supplemental_scores"
SCORE_SUMMARY_DIR = DATA_ROOT / "neon_score_summaries"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db-env-var", default=DB_ENV_VAR)
    parser.add_argument("--provider", choices=("tau2", "hermes", "all"), default="all")
    parser.add_argument("--trace-table", default=TRACE_TABLE)
    parser.add_argument("--turn-table", default=TURN_TABLE)
    parser.add_argument("--summary-table", default=SUMMARY_TABLE)
    parser.add_argument("--tau2-run-table", default=TAU2_RUN_TABLE)
    parser.add_argument("--tau2-score-table", default=SCORE_TABLE)
    parser.add_argument("--supplemental-dir", type=Path, default=SUPPLEMENTAL_SCORE_DIR)
    parser.add_argument("--summary-dir", type=Path, default=SCORE_SUMMARY_DIR)
    parser.add_argument("--skip-traces", action="store_true")
    parser.add_argument("--skip-supplemental-scores", action="store_true")
    parser.add_argument("--skip-summaries", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    load_dotenv()
    providers = ("tau2", "hermes") if args.provider == "all" else (args.provider,)

    trace_rows: list[dict[str, Any]] = []
    turn_rows: list[dict[str, Any]] = []
    if not args.skip_traces:
        for provider in providers:
            traces, provider_id, source = load_product_traces(provider, prefer_neon=False)
            provider_trace_rows, provider_turn_rows = trace_table_rows(traces, provider_id=provider_id, source=source)
            trace_rows.extend(provider_trace_rows)
            turn_rows.extend(provider_turn_rows)

    supplemental_payloads = [] if args.skip_supplemental_scores else load_supplemental_score_payloads(args.supplemental_dir)
    summary_payloads = [] if args.skip_summaries else load_score_summary_payloads(args.summary_dir)

    summary = {
        "trace_rows": len(trace_rows),
        "turn_rows": len(turn_rows),
        "supplemental_files": len(supplemental_payloads),
        "supplemental_score_rows": sum(len(payload["rows"]) for payload in supplemental_payloads),
        "summary_files": len(summary_payloads),
        "summary_run_ids": [payload["run_id"] for payload in summary_payloads],
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    if args.dry_run:
        return

    database_url = configured_database_url(args.db_env_var)
    if not database_url:
        raise RuntimeError(f"{args.db_env_var} is not set")

    with psycopg.connect(database_url, autocommit=False, row_factory=dict_row) as conn:
        if trace_rows:
            ensure_trace_tables(conn, trace_table=args.trace_table, turn_table=args.turn_table)
            replace_trace_rows(conn, trace_table=args.trace_table, turn_table=args.turn_table, trace_rows=trace_rows, turn_rows=turn_rows)
        for payload in supplemental_payloads:
            run_id = str(payload["run_id"])
            first_row = payload["rows"][0] if payload["rows"] else {}
            provider_id = str(first_row.get("provider_id") or "")
            run_table = args.tau2_run_table
            score_table = args.tau2_score_table
            _ensure_tables(conn, run_table=run_table, score_table=score_table)
            ensure_score_run(conn, run_table=run_table, payload=payload)
            replace_supplemental_score_rows(conn, score_table=score_table, payload=payload)
        if summary_payloads:
            ensure_summary_table(conn, summary_table=args.summary_table)
            replace_score_summaries(conn, summary_table=args.summary_table, payloads=summary_payloads)
        conn.commit()


def trace_table_rows(
    traces: Sequence[AuditTrace],
    *,
    provider_id: str,
    source: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    trace_rows: list[dict[str, Any]] = []
    turn_rows: list[dict[str, Any]] = []
    for trace in traces:
        trace_rows.append(
            {
                "provider_id": provider_id,
                "trace_id": trace.trace_id,
                "session_id": trace.session_id,
                "user_id": trace.user_id,
                "domain": trace.domain,
                "task_id": trace.task_id,
                "outcome": trace.outcome,
                "reward": trace.reward,
                "source_model": trace.source_model,
                "user_model": trace.user_model,
                "turn_count": len(trace.turns),
                "labels": dict(trace.labels),
                "metadata": dict(trace.metadata),
                "source": source,
            }
        )
        for turn in trace.turns:
            turn_rows.append(
                {
                    "provider_id": provider_id,
                    "trace_id": trace.trace_id,
                    "turn_id": turn.turn_id,
                    "turn_index": turn.index,
                    "role": turn.role,
                    "content": turn.content,
                    "tool_name": turn.tool_name,
                }
            )
    return trace_rows, turn_rows


def load_supplemental_score_payloads(root: Path = SUPPLEMENTAL_SCORE_DIR) -> list[dict[str, Any]]:
    payloads: list[dict[str, Any]] = []
    for path in sorted(root.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        rows = payload.get("rows")
        if not isinstance(rows, list):
            continue
        payloads.append({**payload, "rows": [dict(row) for row in rows if isinstance(row, Mapping)], "source_path": str(path)})
    return payloads


def load_score_summary_payloads(root: Path = SCORE_SUMMARY_DIR) -> list[dict[str, Any]]:
    payloads: list[dict[str, Any]] = []
    for path in sorted(root.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, Mapping) or not payload.get("run_id"):
            continue
        payloads.append({**dict(payload), "source_path": str(path)})
    return payloads


def ensure_trace_tables(conn: psycopg.Connection, *, trace_table: str, turn_table: str) -> None:
    trace_identifier = sql.Identifier(_safe_identifier(trace_table))
    turn_identifier = sql.Identifier(_safe_identifier(turn_table))
    conn.execute(
        sql.SQL(
            """
            CREATE TABLE IF NOT EXISTS {trace_table} (
                provider_id text NOT NULL,
                trace_id text NOT NULL,
                session_id text NOT NULL,
                user_id text NOT NULL,
                domain text NOT NULL,
                task_id text NOT NULL,
                outcome text NOT NULL,
                reward double precision,
                source_model text,
                user_model text,
                turn_count integer NOT NULL,
                labels jsonb NOT NULL,
                metadata jsonb NOT NULL,
                source text NOT NULL,
                uploaded_at timestamptz NOT NULL DEFAULT now(),
                PRIMARY KEY (provider_id, trace_id)
            )
            """
        ).format(trace_table=trace_identifier)
    )
    conn.execute(
        sql.SQL(
            """
            CREATE TABLE IF NOT EXISTS {turn_table} (
                provider_id text NOT NULL,
                trace_id text NOT NULL,
                turn_id text NOT NULL,
                turn_index integer NOT NULL,
                role text NOT NULL,
                content text NOT NULL,
                tool_name text,
                uploaded_at timestamptz NOT NULL DEFAULT now(),
                PRIMARY KEY (provider_id, trace_id, turn_index)
            )
            """
        ).format(turn_table=turn_identifier)
    )
    for name, table, columns in (
        (f"{trace_table}_user_idx", trace_table, ("provider_id", "user_id")),
        (f"{trace_table}_domain_idx", trace_table, ("provider_id", "domain")),
        (f"{turn_table}_role_idx", turn_table, ("provider_id", "role")),
    ):
        conn.execute(
            sql.SQL("CREATE INDEX IF NOT EXISTS {index} ON {table} ({columns})").format(
                index=sql.Identifier(_safe_identifier(name)),
                table=sql.Identifier(_safe_identifier(table)),
                columns=sql.SQL(", ").join(sql.Identifier(column) for column in columns),
            )
        )


def replace_trace_rows(
    conn: psycopg.Connection,
    *,
    trace_table: str,
    turn_table: str,
    trace_rows: Sequence[Mapping[str, Any]],
    turn_rows: Sequence[Mapping[str, Any]],
) -> None:
    providers = sorted({str(row["provider_id"]) for row in trace_rows})
    trace_identifier = sql.Identifier(_safe_identifier(trace_table))
    turn_identifier = sql.Identifier(_safe_identifier(turn_table))
    conn.execute(sql.SQL("DELETE FROM {table} WHERE provider_id = ANY(%s)").format(table=turn_identifier), (providers,))
    conn.execute(sql.SQL("DELETE FROM {table} WHERE provider_id = ANY(%s)").format(table=trace_identifier), (providers,))
    copy_rows(conn, trace_table, trace_rows, ("provider_id", "trace_id", "session_id", "user_id", "domain", "task_id", "outcome", "reward", "source_model", "user_model", "turn_count", "labels", "metadata", "source"))
    copy_rows(conn, turn_table, turn_rows, ("provider_id", "trace_id", "turn_id", "turn_index", "role", "content", "tool_name"))


def ensure_score_run(conn: psycopg.Connection, *, run_table: str, payload: Mapping[str, Any]) -> None:
    run_id = str(payload["run_id"])
    existing = conn.execute(
        sql.SQL("SELECT run_id FROM {table} WHERE run_id = %s").format(table=sql.Identifier(_safe_identifier(run_table))),
        (run_id,),
    ).fetchone()
    if existing:
        return
    rows = payload.get("rows") if isinstance(payload.get("rows"), list) else []
    first_row = rows[0] if rows else {}
    provider_id = str(first_row.get("provider_id") or "unknown")
    source = str(first_row.get("source") or payload.get("source") or "local supplemental scores")
    conn.execute(
        sql.SQL(
            """
            INSERT INTO {table} (
                run_id, workflow_name, provider_id, source, artifact_volume, artifact_root,
                capture_artifact_id, projection_artifact_id, emotion_artifact_id,
                high_stakes_artifact_ids, trace_count, record_count, score_row_count, metadata
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
        ).format(table=sql.Identifier(_safe_identifier(run_table))),
        (
            run_id,
            "behavior_audit_local_supplemental_scores",
            provider_id,
            source,
            "local",
            str(payload.get("source_path") or ""),
            "",
            str(payload.get("projection", {}).get("trait_vector_repo") if isinstance(payload.get("projection"), Mapping) else ""),
            "",
            [],
            int(payload.get("trace_count") or 0),
            0,
            len(rows),
            Jsonb({key: value for key, value in payload.items() if key != "rows"}),
        ),
    )


def replace_supplemental_score_rows(conn: psycopg.Connection, *, score_table: str, payload: Mapping[str, Any]) -> None:
    rows = payload.get("rows")
    if not isinstance(rows, list) or not rows:
        return
    run_id = str(payload["run_id"])
    artifact_ids = sorted({str(row.get("artifact_id") or "") for row in rows if row.get("artifact_id")})
    score_identifier = sql.Identifier(_safe_identifier(score_table))
    conn.execute(
        sql.SQL("DELETE FROM {table} WHERE run_id = %s AND artifact_id = ANY(%s)").format(table=score_identifier),
        (run_id, artifact_ids),
    )
    copy_rows(conn, score_table, rows, SCORE_COLUMNS)


def ensure_summary_table(conn: psycopg.Connection, *, summary_table: str) -> None:
    summary_identifier = sql.Identifier(_safe_identifier(summary_table))
    conn.execute(
        sql.SQL(
            """
            CREATE TABLE IF NOT EXISTS {summary_table} (
                run_id text PRIMARY KEY,
                kind text NOT NULL,
                version integer,
                score_inventory jsonb NOT NULL,
                score_surface jsonb NOT NULL,
                module_scores jsonb NOT NULL,
                source_path text NOT NULL,
                payload jsonb NOT NULL,
                uploaded_at timestamptz NOT NULL DEFAULT now()
            )
            """
        ).format(summary_table=summary_identifier)
    )


def replace_score_summaries(conn: psycopg.Connection, *, summary_table: str, payloads: Sequence[Mapping[str, Any]]) -> None:
    summary_identifier = sql.Identifier(_safe_identifier(summary_table))
    for payload in payloads:
        conn.execute(sql.SQL("DELETE FROM {table} WHERE run_id = %s").format(table=summary_identifier), (payload["run_id"],))
        conn.execute(
            sql.SQL(
                """
                INSERT INTO {table} (
                    run_id, kind, version, score_inventory, score_surface, module_scores, source_path, payload
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """
            ).format(table=summary_identifier),
            (
                payload["run_id"],
                payload.get("kind") or "behavior_audit_score_summary",
                payload.get("version"),
                Jsonb(payload.get("score_inventory") or {}),
                Jsonb(payload.get("score_surface") or {}),
                Jsonb(payload.get("module_scores") or []),
                payload.get("source_path") or "",
                Jsonb({key: value for key, value in payload.items() if key != "source_path"}),
            ),
        )


def copy_rows(
    conn: psycopg.Connection,
    table_name: str,
    rows: Sequence[Mapping[str, Any]],
    columns: Sequence[str],
) -> None:
    if not rows:
        return
    with conn.cursor().copy(
        sql.SQL("COPY {table} ({columns}) FROM STDIN").format(
            table=sql.Identifier(_safe_identifier(table_name)),
            columns=sql.SQL(", ").join(sql.Identifier(column) for column in columns),
        )
    ) as copy:
        for row in rows:
            copy.write_row(tuple(_copy_value(row.get(column)) for column in columns))


if __name__ == "__main__":
    main()
