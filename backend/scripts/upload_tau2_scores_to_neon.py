from __future__ import annotations

"""Upload Persona Audit Tau2 score artifacts into Neon."""

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import psycopg
from psycopg import sql
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from pipelines_v2.api import ModalVolumeStore, TransferPolicy
from backend.api.scoring_spaces import trace_scoring_records
from backend.api.trace_source import load_product_traces
from backend.paths import DATABASE_URL_ENV, LEGACY_DATABASE_URL_ENV, configured_database_url, load_dotenv


DB_ENV_VAR = DATABASE_URL_ENV
LEGACY_DB_ENV_VAR = LEGACY_DATABASE_URL_ENV
ARTIFACT_VOLUME = "xenon-data"
ARTIFACT_ROOT = "/data/artifacts/behavior_audit_tau2_scoring_v1"

DEFAULT_RUN_ID = "wr_667d470028fd_c294c37f"
DEFAULT_CAPTURE_ARTIFACT_ID = "capture_1_4e5712e65e19"
DEFAULT_PROJECTION_ARTIFACT_ID = "projection_1_3e11578a"
DEFAULT_EMOTION_ARTIFACT_ID = "emotion_score_1_5e3c4ee9"
DEFAULT_HIGH_STAKES_ARTIFACT_IDS: tuple[str, ...] = (
    "persisted_probe_inference_1_0e0e404f",
    "persisted_probe_inference_1_4c831bcd",
    "persisted_probe_inference_1_92ef3bcd",
    "persisted_probe_inference_1_346eab61",
    "persisted_probe_inference_1_15fe2245",
    "persisted_probe_inference_1_bad5100f",
    "persisted_probe_inference_1_0579a237",
    "persisted_probe_inference_1_0e3118ad",
    "persisted_probe_inference_1_a39c79a0",
    "persisted_probe_inference_1_8a1b9711",
    "persisted_probe_inference_1_3c984c19",
    "persisted_probe_inference_1_8791c256",
    "persisted_probe_inference_1_fcea05e3",
)

RUN_TABLE = "behavior_audit_tau2_score_runs"
SCORE_TABLE = "behavior_audit_tau2_score_rows"

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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", default=DEFAULT_RUN_ID)
    parser.add_argument("--capture-artifact-id", default=DEFAULT_CAPTURE_ARTIFACT_ID)
    parser.add_argument("--projection-artifact-id", default=DEFAULT_PROJECTION_ARTIFACT_ID)
    parser.add_argument("--emotion-artifact-id", default=DEFAULT_EMOTION_ARTIFACT_ID)
    parser.add_argument("--high-stakes-artifact-id", action="append", dest="high_stakes_artifact_ids")
    parser.add_argument("--artifact-volume", default=ARTIFACT_VOLUME)
    parser.add_argument("--artifact-root", default=ARTIFACT_ROOT)
    parser.add_argument("--db-env-var", default=DB_ENV_VAR)
    parser.add_argument("--run-table", default=RUN_TABLE)
    parser.add_argument("--score-table", default=SCORE_TABLE)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    load_dotenv()

    traces, provider_id, source = load_product_traces()
    records = trace_scoring_records(traces)
    record_index = _record_index(records, provider_id=provider_id, source=source)
    high_stakes_artifact_ids = tuple(args.high_stakes_artifact_ids or DEFAULT_HIGH_STAKES_ARTIFACT_IDS)
    store = ModalVolumeStore(
        name=args.artifact_volume,
        root=args.artifact_root,
        transfer_policy=TransferPolicy(allow_large_transfer=True),
    )

    artifact_loads = [
        ArtifactLoad(args.projection_artifact_id, "assistant_axis", _load_result(store, args.projection_artifact_id)),
        ArtifactLoad(args.emotion_artifact_id, "emotion", _load_result(store, args.emotion_artifact_id)),
        *[
            ArtifactLoad(artifact_id, "high_stakes", _load_result(store, artifact_id))
            for artifact_id in high_stakes_artifact_ids
        ],
    ]
    score_rows = [
        row
        for load in artifact_loads
        for row in _score_rows(
            load,
            run_id=args.run_id,
            record_index=record_index,
            provider_id=provider_id,
            source=source,
        )
    ]
    family_counts: dict[str, int] = {}
    for row in score_rows:
        family_counts[row["score_family"]] = family_counts.get(row["score_family"], 0) + 1

    run_row = {
        "run_id": args.run_id,
        "workflow_name": "behavior_audit_tau2_scoring_v1",
        "provider_id": provider_id,
        "source": source,
        "artifact_volume": args.artifact_volume,
        "artifact_root": args.artifact_root,
        "capture_artifact_id": args.capture_artifact_id,
        "projection_artifact_id": args.projection_artifact_id,
        "emotion_artifact_id": args.emotion_artifact_id,
        "high_stakes_artifact_ids": list(high_stakes_artifact_ids),
        "trace_count": len(traces),
        "record_count": len(records),
        "score_row_count": len(score_rows),
        "metadata": {
            "score_family_counts": family_counts,
            "artifacts": [
                {
                    "artifact_id": load.artifact_id,
                    "family": load.family,
                    "kind": load.payload.get("kind"),
                    "summary": load.payload.get("summary"),
                }
                for load in artifact_loads
            ],
        },
    }

    print(
        json.dumps(
            {
                "run": run_row,
                "score_family_counts": family_counts,
            },
            indent=2,
            sort_keys=True,
        )
    )
    if args.dry_run:
        return

    database_url = configured_database_url(args.db_env_var)
    if not database_url:
        raise RuntimeError(f"{args.db_env_var} is not set")
    with psycopg.connect(database_url, autocommit=False, row_factory=dict_row) as conn:
        _ensure_tables(conn, run_table=args.run_table, score_table=args.score_table)
        _replace_run(conn, run_table=args.run_table, score_table=args.score_table, run_row=run_row, score_rows=score_rows)
        conn.commit()
    print(f"uploaded {len(score_rows)} score rows for {args.run_id}")


def _record_index(records: Sequence[Mapping[str, Any]], *, provider_id: str, source: str) -> dict[str, dict[str, Any]]:
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


def _load_result(store: ModalVolumeStore, artifact_id: str) -> Mapping[str, Any]:
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


def _score_rows(
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


def _ensure_tables(conn: psycopg.Connection, *, run_table: str, score_table: str) -> None:
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


def _replace_run(
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
            copy.write_row(tuple(_copy_value(row.get(column)) for column in SCORE_COLUMNS))


def _copy_value(value: Any) -> Any:
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
