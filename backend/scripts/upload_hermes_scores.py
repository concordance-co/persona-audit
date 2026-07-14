"""Import Hermes score artifacts into local cache and Neon.

The Hermes workflow emits four score artifacts:

- visible assistant response traits
- visible assistant response emotions
- assistant reasoning traits
- assistant reasoning emotions

Visible response scores use the canonical ``assistant_axis`` and ``emotion``
families so existing Persona Audit baselines can read them. Reasoning scores
use separate families so they can power Thought-vs-Said views without being
mixed into ordinary response baselines.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import psycopg
from pipelines_v2.api import ModalVolumeStore, TransferPolicy
from psycopg.rows import dict_row

from backend.api.scores import HERMES_DEFAULT_RUN_ID
from backend.api.scoring_spaces import trace_scoring_records
from backend.api.trace_source import load_product_traces
from backend.paths import DATA_ROOT, configured_database_url, load_dotenv
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
from backend.scripts.upload_tau2_scores import DB_ENV_VAR
from backend.workflows.common import artifact_volume_name

ARTIFACT_VOLUME = artifact_volume_name()
ARTIFACT_ROOT = "/data/artifacts/persona_audit_hermes_scoring_v1"
WORKFLOW_NAME = "persona_audit_hermes_scoring_v1"

RUN_TABLE = "persona_audit_hermes_score_runs"
SCORE_TABLE = "persona_audit_hermes_score_rows"
SUPPLEMENTAL_SCORE_DIR = DATA_ROOT / "supplemental_scores"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", default=HERMES_DEFAULT_RUN_ID)
    parser.add_argument("--workflow-run-id", default="")
    parser.add_argument("--capture-artifact-id", required=True)
    parser.add_argument("--projection-artifact-id", required=True)
    parser.add_argument("--emotion-artifact-id", required=True)
    parser.add_argument("--reasoning-projection-artifact-id", required=True)
    parser.add_argument("--reasoning-emotion-artifact-id", required=True)
    parser.add_argument("--artifact-volume", default=ARTIFACT_VOLUME)
    parser.add_argument("--artifact-root", default=ARTIFACT_ROOT)
    parser.add_argument("--db-env-var", default=DB_ENV_VAR)
    parser.add_argument("--run-table", default=RUN_TABLE)
    parser.add_argument("--score-table", default=SCORE_TABLE)
    parser.add_argument("--local-cache-dir", type=Path, default=SUPPLEMENTAL_SCORE_DIR)
    parser.add_argument("--skip-local-cache", action="store_true")
    parser.add_argument("--skip-neon", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    load_dotenv()
    payload = build_import_payload(
        run_id=args.run_id,
        workflow_run_id=args.workflow_run_id,
        capture_artifact_id=args.capture_artifact_id,
        projection_artifact_id=args.projection_artifact_id,
        emotion_artifact_id=args.emotion_artifact_id,
        reasoning_projection_artifact_id=args.reasoning_projection_artifact_id,
        reasoning_emotion_artifact_id=args.reasoning_emotion_artifact_id,
        artifact_volume=args.artifact_volume,
        artifact_root=args.artifact_root,
    )
    print(
        json.dumps(
            {
                "run": {key: value for key, value in payload["run"].items() if key != "metadata"},
                "score_family_counts": payload["score_family_counts"],
                "local_cache_path": str(_local_cache_path(args.local_cache_dir, args.run_id)),
            },
            indent=2,
            sort_keys=True,
        )
    )
    if args.dry_run:
        return

    if not args.skip_local_cache:
        write_local_cache(payload["local_cache"], args.local_cache_dir)

    if args.skip_neon:
        return
    database_url = configured_database_url(args.db_env_var)
    if not database_url:
        raise RuntimeError(f"{args.db_env_var} is not set")
    with psycopg.connect(database_url, autocommit=False, row_factory=dict_row) as conn:
        ensure_tables(conn, run_table=args.run_table, score_table=args.score_table)
        replace_run(
            conn,
            run_table=args.run_table,
            score_table=args.score_table,
            run_row=payload["run"],
            score_rows=payload["score_rows"],
        )
        conn.commit()
    print(f"uploaded {len(payload['score_rows'])} Hermes score rows for {args.run_id}")


def build_import_payload(
    *,
    run_id: str,
    workflow_run_id: str,
    capture_artifact_id: str,
    projection_artifact_id: str,
    emotion_artifact_id: str,
    reasoning_projection_artifact_id: str,
    reasoning_emotion_artifact_id: str,
    artifact_volume: str,
    artifact_root: str,
) -> dict[str, Any]:
    traces, provider_id, source = load_product_traces("hermes", prefer_neon=False)
    records = trace_scoring_records(traces)
    record_index = build_record_index(records, provider_id=provider_id, source=source)
    store = ModalVolumeStore(
        name=artifact_volume,
        root=artifact_root,
        transfer_policy=TransferPolicy(allow_large_transfer=True),
    )
    artifact_loads = [
        ArtifactLoad(projection_artifact_id, "assistant_axis", load_result(store, projection_artifact_id)),
        ArtifactLoad(emotion_artifact_id, "emotion", load_result(store, emotion_artifact_id)),
        ArtifactLoad(
            reasoning_projection_artifact_id,
            "reasoning_assistant_axis",
            load_result(store, reasoning_projection_artifact_id),
        ),
        ArtifactLoad(
            reasoning_emotion_artifact_id, "reasoning_emotion", load_result(store, reasoning_emotion_artifact_id)
        ),
    ]
    score_rows = [
        row
        for load in artifact_loads
        for row in score_rows_from_artifact(
            load,
            run_id=run_id,
            record_index=record_index,
            provider_id=provider_id,
            source=source,
        )
    ]
    family_counts: dict[str, int] = {}
    for row in score_rows:
        family_counts[str(row["score_family"])] = family_counts.get(str(row["score_family"]), 0) + 1

    run_row = {
        "run_id": run_id,
        "workflow_name": WORKFLOW_NAME,
        "provider_id": provider_id,
        "source": source,
        "artifact_volume": artifact_volume,
        "artifact_root": artifact_root,
        "capture_artifact_id": capture_artifact_id,
        "projection_artifact_id": projection_artifact_id,
        "emotion_artifact_id": emotion_artifact_id,
        "high_stakes_artifact_ids": [],
        "trace_count": len(traces),
        "record_count": len(records),
        "score_row_count": len(score_rows),
        "metadata": {
            "workflow_run_id": workflow_run_id,
            "reasoning_projection_artifact_id": reasoning_projection_artifact_id,
            "reasoning_emotion_artifact_id": reasoning_emotion_artifact_id,
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
    return {
        "run": run_row,
        "score_rows": score_rows,
        "score_family_counts": family_counts,
        "local_cache": {
            "run_id": run_id,
            "workflow_name": WORKFLOW_NAME,
            "provider_id": provider_id,
            "source": source,
            "trace_count": len(traces),
            "record_count": len(records),
            "score_family_counts": family_counts,
            "metadata": run_row["metadata"],
            "rows": score_rows,
        },
    }


def write_local_cache(payload: Mapping[str, Any], root: Path = SUPPLEMENTAL_SCORE_DIR) -> Path:
    run_id = str(payload["run_id"])
    path = _local_cache_path(root, run_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f"{path.name}.tmp")
    tmp_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    tmp_path.replace(path)
    print(f"wrote local Hermes score cache: {path}")
    return path


def _local_cache_path(root: Path, run_id: str) -> Path:
    return root / f"{run_id}_assistant_trait_scores.json"


if __name__ == "__main__":
    main()
