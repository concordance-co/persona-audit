"""Upload Persona Audit Tau2 score artifacts into Neon."""

from __future__ import annotations

import argparse
import json

import psycopg
from pipelines_v2.api import ModalVolumeStore, TransferPolicy
from psycopg.rows import dict_row

from backend.api.scoring_spaces import trace_scoring_records
from backend.api.trace_source import load_product_traces
from backend.paths import DATABASE_URL_ENV, configured_database_url, load_dotenv
from backend.scores_io import (
    ArtifactLoad,
    ensure_tables,
    load_result,
    replace_run,
    score_rows_from_artifact,
)
from backend.scores_io import (
    record_index as build_record_index,
)
from backend.workflows.common import artifact_volume_name

DB_ENV_VAR = DATABASE_URL_ENV
ARTIFACT_VOLUME = artifact_volume_name()
# Historical default: the shipped run and its artifact ids below predate the
# persona_audit rename and live at this root on the maintainer volume.
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

RUN_TABLE = "persona_audit_tau2_score_runs"
SCORE_TABLE = "persona_audit_tau2_score_rows"


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
    record_index = build_record_index(records, provider_id=provider_id, source=source)
    high_stakes_artifact_ids = tuple(args.high_stakes_artifact_ids or DEFAULT_HIGH_STAKES_ARTIFACT_IDS)
    store = ModalVolumeStore(
        name=args.artifact_volume,
        root=args.artifact_root,
        transfer_policy=TransferPolicy(allow_large_transfer=True),
    )

    artifact_loads = [
        ArtifactLoad(args.projection_artifact_id, "assistant_axis", load_result(store, args.projection_artifact_id)),
        ArtifactLoad(args.emotion_artifact_id, "emotion", load_result(store, args.emotion_artifact_id)),
        *[
            ArtifactLoad(artifact_id, "high_stakes", load_result(store, artifact_id))
            for artifact_id in high_stakes_artifact_ids
        ],
    ]
    score_rows = [
        row
        for load in artifact_loads
        for row in score_rows_from_artifact(
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
        "workflow_name": "behavior_audit_tau2_scoring_v1",  # historical: matches the default artifacts
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
        ensure_tables(conn, run_table=args.run_table, score_table=args.score_table)
        replace_run(
            conn, run_table=args.run_table, score_table=args.score_table, run_row=run_row, score_rows=score_rows
        )
        conn.commit()
    print(f"uploaded {len(score_rows)} score rows for {args.run_id}")


if __name__ == "__main__":
    main()
