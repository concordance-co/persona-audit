"""Shared score-artifact IO: pull Modal score artifacts and write score tables.

Used by every upload script (backend/scripts/upload_*_scores.py,
upload_local_data.py) and the demo score-cache builder. The canonical
score-row shape is ``SCORE_COLUMNS``; ``ensure_tables`` creates the run/score
tables and ``replace_run`` idempotently swaps a run's rows via COPY.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import psycopg
from pipelines_v2.api import ModalVolumeStore
from psycopg import sql
from psycopg.types.json import Jsonb

SCORE_COLUMNS: tuple[str, ...] = (
    "run_id",
    "artifact_id",
    "score_family",
    "coordinate",
    "example_key",
    "trace_id",
    "turn_index",
    "provider_id",
    "source",
    "domain",
    "task_id",
    "outcome",
    "reward",
    "is_high_stakes_candidate",
    "source_model",
    "user_model",
    "layer",
    "metric",
    "score",
    "probability",
    "prediction",
    "positive_class",
    "slice_name",
    "slice_index",
    "slice_token_count",
    "role",
    "unit",
    "summary",
    "row_payload",
)


@dataclass(frozen=True)
class ArtifactLoad:
    artifact_id: str
    family: str
    payload: Mapping[str, Any]


def record_index(records: Sequence[Mapping[str, Any]], *, provider_id: str, source: str) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for record in records:
        labels = _mapping(record.get("labels"))
        metadata = _mapping(record.get("metadata"))
        example_id = str(record["example_id"])
        index[example_id] = {
            "trace_id": str(record.get("trace_id") or ""),
            "turn_index": _optional_int(record.get("turn_index")),
            "provider_id": provider_id,
            "source": source,
            "domain": _optional_text(labels.get("domain")),
            "task_id": _optional_text(labels.get("task_id")),
            "outcome": _optional_text(labels.get("outcome")),
            "reward": _optional_float(labels.get("reward")),
            "is_high_stakes_candidate": _optional_bool(labels.get("is_high_stakes_candidate")),
            "source_model": _optional_text(metadata.get("source_model")),
            "user_model": _optional_text(metadata.get("user_model")),
        }
    return index


def load_result(store: ModalVolumeStore, artifact_id: str) -> Mapping[str, Any]:
    payload = store.read_json_ref(
        {
            "store": "modal_volume",
            "name": store.name,
            "path": f"{store.root.rstrip('/')}/{artifact_id}/result.json",
            "format": "json",
        }
    )
    if not isinstance(payload, Mapping):
        raise TypeError(f"{artifact_id}/result.json is not a JSON object")
    return payload


def score_rows_from_artifact(
    load: ArtifactLoad,
    *,
    run_id: str,
    record_index: Mapping[str, Mapping[str, Any]],
    provider_id: str,
    source: str,
) -> Iterable[dict[str, Any]]:
    rows = load.payload.get("rows")
    if not isinstance(rows, Sequence):
        raise TypeError(f"{load.artifact_id} result rows are not a sequence")
    summary_by_key = _summary_index(load.payload.get("example_summaries"))
    for raw_row in rows:
        if not isinstance(raw_row, Mapping):
            continue
        example_key = str(raw_row.get("example_key") or "")
        if not example_key:
            continue
        metadata = dict(record_index.get(example_key) or {"provider_id": provider_id, "source": source})
        coordinate = _coordinate(load, raw_row)
        summary = summary_by_key.get((example_key, coordinate))
        yield {
            "run_id": run_id,
            "artifact_id": load.artifact_id,
            "score_family": load.family,
            "coordinate": coordinate,
            "example_key": example_key,
            "trace_id": metadata.get("trace_id"),
            "turn_index": metadata.get("turn_index"),
            "provider_id": metadata.get("provider_id"),
            "source": metadata.get("source"),
            "domain": metadata.get("domain"),
            "task_id": metadata.get("task_id"),
            "outcome": metadata.get("outcome"),
            "reward": metadata.get("reward"),
            "is_high_stakes_candidate": metadata.get("is_high_stakes_candidate"),
            "source_model": metadata.get("source_model"),
            "user_model": metadata.get("user_model"),
            "layer": _optional_int(raw_row.get("layer")),
            "metric": "score",
            "score": _optional_float(raw_row.get("score")),
            "probability": _optional_float(raw_row.get("probability")),
            "prediction": _optional_text(raw_row.get("prediction")),
            "positive_class": _optional_text(raw_row.get("positive_class")),
            "slice_name": _optional_text(raw_row.get("slice_name")),
            "slice_index": _optional_int(raw_row.get("slice_index")),
            "slice_token_count": _optional_int(raw_row.get("slice_token_count")),
            "role": _optional_text(raw_row.get("role")),
            "unit": _optional_text(raw_row.get("unit")),
            "summary": summary,
            "row_payload": dict(raw_row),
        }


def _summary_index(value: Any) -> dict[tuple[str, str], dict[str, Any]]:
    if not isinstance(value, Sequence):
        return {}
    indexed: dict[tuple[str, str], dict[str, Any]] = {}
    for item in value:
        if not isinstance(item, Mapping):
            continue
        example_key = str(item.get("example_key") or "")
        coordinate = str(item.get("coordinate") or "")
        if example_key and coordinate:
            indexed[(example_key, coordinate)] = dict(item)
    return indexed


def _coordinate(load: ArtifactLoad, row: Mapping[str, Any]) -> str:
    if load.family == "high_stakes":
        return str(row.get("probe") or load.payload.get("probe", {}).get("name") or load.artifact_id)
    return str(row.get("coordinate") or load.artifact_id)


def ensure_tables(conn: psycopg.Connection, *, run_table: str, score_table: str) -> None:
    run_identifier = sql.Identifier(run_table)
    score_identifier = sql.Identifier(score_table)
    conn.execute(
        sql.SQL(
            """
            CREATE TABLE IF NOT EXISTS {run_table} (
                run_id text PRIMARY KEY,
                workflow_name text NOT NULL,
                provider_id text NOT NULL,
                source text NOT NULL,
                artifact_volume text NOT NULL,
                artifact_root text NOT NULL,
                capture_artifact_id text NOT NULL,
                projection_artifact_id text NOT NULL,
                emotion_artifact_id text NOT NULL,
                high_stakes_artifact_ids text[] NOT NULL,
                trace_count integer NOT NULL,
                record_count integer NOT NULL,
                score_row_count integer NOT NULL,
                metadata jsonb NOT NULL,
                uploaded_at timestamptz NOT NULL DEFAULT now()
            )
            """
        ).format(run_table=run_identifier)
    )
    conn.execute(
        sql.SQL(
            """
            CREATE TABLE IF NOT EXISTS {score_table} (
                run_id text NOT NULL REFERENCES {run_table}(run_id) ON DELETE CASCADE,
                artifact_id text NOT NULL,
                score_family text NOT NULL,
                coordinate text NOT NULL,
                example_key text NOT NULL,
                trace_id text,
                turn_index integer,
                provider_id text,
                source text,
                domain text,
                task_id text,
                outcome text,
                reward double precision,
                is_high_stakes_candidate boolean,
                source_model text,
                user_model text,
                layer integer,
                metric text NOT NULL,
                score double precision,
                probability double precision,
                prediction text,
                positive_class text,
                slice_name text,
                slice_index integer,
                slice_token_count integer,
                role text,
                unit text,
                summary jsonb,
                row_payload jsonb NOT NULL,
                uploaded_at timestamptz NOT NULL DEFAULT now(),
                PRIMARY KEY (run_id, artifact_id, score_family, coordinate, example_key, layer, metric)
            )
            """
        ).format(score_table=score_identifier, run_table=run_identifier)
    )
    for name, columns in {
        f"{score_table}_trace_idx": ("run_id", "trace_id", "turn_index"),
        f"{score_table}_family_idx": ("run_id", "score_family", "coordinate"),
        f"{score_table}_example_idx": ("run_id", "example_key"),
    }.items():
        conn.execute(
            sql.SQL("CREATE INDEX IF NOT EXISTS {index} ON {table} ({columns})").format(
                index=sql.Identifier(name),
                table=score_identifier,
                columns=sql.SQL(", ").join(sql.Identifier(column) for column in columns),
            )
        )


def replace_run(
    conn: psycopg.Connection,
    *,
    run_table: str,
    score_table: str,
    run_row: Mapping[str, Any],
    score_rows: Sequence[Mapping[str, Any]],
) -> None:
    run_identifier = sql.Identifier(run_table)
    score_identifier = sql.Identifier(score_table)
    conn.execute(sql.SQL("DELETE FROM {table} WHERE run_id = %s").format(table=run_identifier), (run_row["run_id"],))
    conn.execute(
        sql.SQL(
            """
            INSERT INTO {table} (
                run_id, workflow_name, provider_id, source, artifact_volume, artifact_root,
                capture_artifact_id, projection_artifact_id, emotion_artifact_id,
                high_stakes_artifact_ids, trace_count, record_count, score_row_count, metadata
            )
            VALUES (
                %(run_id)s, %(workflow_name)s, %(provider_id)s, %(source)s, %(artifact_volume)s, %(artifact_root)s,
                %(capture_artifact_id)s, %(projection_artifact_id)s, %(emotion_artifact_id)s,
                %(high_stakes_artifact_ids)s, %(trace_count)s, %(record_count)s, %(score_row_count)s, %(metadata)s
            )
            """
        ).format(table=run_identifier),
        {**run_row, "metadata": Jsonb(run_row["metadata"])},
    )
    if not score_rows:
        return
    column_list = sql.SQL(", ").join(sql.Identifier(column) for column in SCORE_COLUMNS)
    with conn.cursor().copy(
        sql.SQL("COPY {table} ({columns}) FROM STDIN").format(table=score_identifier, columns=column_list)
    ) as copy:
        for row in score_rows:
            copy.write_row(tuple(copy_value(row.get(column)) for column in SCORE_COLUMNS))


def copy_value(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return Jsonb(value)
    return value


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    return int(value)


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    return float(value)


def _optional_bool(value: Any) -> bool | None:
    if value is None:
        return None
    return bool(value)
