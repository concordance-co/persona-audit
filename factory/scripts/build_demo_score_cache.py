"""Build the local score cache for the persona-demo dashboard (no Postgres).

The dashboard reads per-trace scores from a supplemental score-rows file when no
database is configured (backend/api/scores/offline.py:_supplemental_score_rows).
This script transforms the Stage 2 Modal score artifacts — already cached
locally under artifacts/demo_hillclimb/modal_cache/ during the scoring run —
into that file, reusing the exact row-shaping from upload_tau2_scores so
the format matches production. No Modal or Neon access required.

    uv run python -m factory.scripts.build_demo_score_cache

Emits data/supplemental_scores/<run_id>_assistant_trait_scores.json.gz. Point the
dashboard at it with PERSONA_AUDIT_SCORE_RUN_ID=<run_id> (printed at the end).
"""

from __future__ import annotations

import gzip
import json
from collections import Counter

from backend.api.providers.persona_demo import SOURCE_LABEL as PERSONA_DEMO_SOURCE
from backend.api.scoring_spaces import trace_scoring_records
from backend.api.trace_source import load_product_traces
from backend.paths import REPO_ROOT
from backend.scores_io import ArtifactLoad, score_rows_from_artifact
from backend.scores_io import record_index as build_record_index

STAGE2_DIR = REPO_ROOT / "data" / "demo" / "stage2"
CACHE_ROOT = REPO_ROOT / "artifacts" / "demo_hillclimb" / "modal_cache" / "behavior_audit_demo_scoring_v1"
OUT_DIR = REPO_ROOT / "data" / "supplemental_scores"

# Families to materialize locally. Emotion rows are required for the public
# dashboard's cluster baselines, session trajectories, and concept spectrum.
# Projection rows are compacted below so the complete 171-concept artifact can
# ship without copying the artifact's redundant per-row summaries.
_FAMILY_BY_STEP_PREFIX = {
    "score_assistant_axis": "assistant_axis",
    "score_emotions": "emotion",
    "score_high_stakes": "high_stakes",
}


def _family(step_name: str) -> str | None:
    for prefix, family in _FAMILY_BY_STEP_PREFIX.items():
        if step_name.startswith(prefix):
            return family
    return None


def _compact_row(row: dict[str, object]) -> dict[str, object]:
    """Drop redundant projection payloads while preserving serving fields."""

    if row.get("score_family") not in {"assistant_axis", "emotion"}:
        return row
    compact = {key: value for key, value in row.items() if key not in {"summary", "row_payload"} and value is not None}
    compact["row_payload"] = {}
    return compact


def main() -> int:
    score_run = json.loads((STAGE2_DIR / "score_run.json").read_text(encoding="utf-8"))
    run_id = str(score_run["run_id"])

    traces, provider_id, source = load_product_traces("persona_demo")
    records = trace_scoring_records(traces)
    record_index = build_record_index(records, provider_id=provider_id, source=source)

    loads: list[ArtifactLoad] = []
    for step_name, step in score_run.get("steps", {}).items():
        family = _family(step_name)
        if family is None:
            continue
        artifact_id = str(step.get("artifact_id") or "")
        result_path = CACHE_ROOT / artifact_id / "result.json"
        if not result_path.exists():
            print(f"skip {step_name}: cached artifact missing at {result_path}")
            continue
        payload = json.loads(result_path.read_text(encoding="utf-8"))
        loads.append(ArtifactLoad(artifact_id, family, payload))

    rows = [
        _compact_row(row)
        for load in loads
        for row in score_rows_from_artifact(
            load, run_id=run_id, record_index=record_index, provider_id=provider_id, source=source
        )
    ]
    if not rows:
        print("no score rows built; check that Stage 2 artifacts are cached locally")
        return 1

    family_counts = Counter(str(row["score_family"]) for row in rows)
    matched = sum(1 for row in rows if row.get("trace_id"))
    coordinates = sorted(
        {str(row["coordinate"]) for row in rows if row["score_family"] in {"assistant_axis", "emotion"}}
    )

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / f"{run_id}_assistant_trait_scores.json.gz"
    serialized = json.dumps(
        {
            "kind": "persona_audit_supplemental_score_rows",
            "version": 1,
            "run_id": run_id,
            "source": PERSONA_DEMO_SOURCE,
            "score_family": "assistant_axis+emotion",
            "coordinates": coordinates,
            "trace_count": len(traces),
            "row_count": len(rows),
            "score_family_counts": dict(family_counts),
            "rows": rows,
        },
        separators=(",", ":"),
    ).encode("utf-8")
    out_path.write_bytes(gzip.compress(serialized, compresslevel=9, mtime=0))

    print(f"wrote {len(rows)} rows ({dict(family_counts)}) -> {out_path}")
    print(f"trace-joined rows: {matched}/{len(rows)}; projection coordinates: {len(coordinates)}")
    print(f"point the dashboard at it: PERSONA_AUDIT_SCORE_RUN_ID={run_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
