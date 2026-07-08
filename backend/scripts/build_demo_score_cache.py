"""Build the local score cache for the persona-demo dashboard (no Postgres).

The dashboard reads per-trace scores from a supplemental score-rows file when no
database is configured (backend/api/neon_scores.py:_supplemental_score_rows).
This script transforms the Stage 2 Modal score artifacts — already cached
locally under artifacts/demo_hillclimb/modal_cache/ during the scoring run —
into that file, reusing the exact row-shaping from upload_tau2_scores_to_neon so
the format matches production. No Modal or Neon access required.

    uv run python -m backend.scripts.build_demo_score_cache

Emits data/supplemental_scores/<run_id>_assistant_trait_scores.json. Point the
dashboard at it with BEHAVIOR_AUDIT_SCORE_RUN_ID=<run_id> (printed at the end).
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from backend.api.scoring_spaces import trace_scoring_records
from backend.api.trace_source import PERSONA_DEMO_SOURCE, load_product_traces
from backend.paths import REPO_ROOT
from backend.scripts.upload_tau2_scores_to_neon import ArtifactLoad, _record_index, _score_rows

STAGE2_DIR = REPO_ROOT / "data" / "demo" / "stage2"
CACHE_ROOT = REPO_ROOT / "artifacts" / "demo_hillclimb" / "modal_cache" / "behavior_audit_demo_scoring_v1"
OUT_DIR = REPO_ROOT / "data" / "supplemental_scores"

# Families to materialize locally. The emotion space is intentionally excluded:
# it is ~51k rows for this dataset and would bloat the shipped repo; the trait
# axis is the primary persona-separation surface and high-stakes probes are the
# safety surface. Emotion remains available via the full artifacts if needed.
_FAMILY_BY_STEP_PREFIX = {
    "score_assistant_axis": "assistant_axis",
    "score_high_stakes": "high_stakes",
}


def _family(step_name: str) -> str | None:
    for prefix, family in _FAMILY_BY_STEP_PREFIX.items():
        if step_name.startswith(prefix):
            return family
    return None


def main() -> int:
    score_run = json.loads((STAGE2_DIR / "score_run.json").read_text(encoding="utf-8"))
    run_id = str(score_run["run_id"])

    traces, provider_id, source = load_product_traces("persona_demo")
    records = trace_scoring_records(traces)
    record_index = _record_index(records, provider_id=provider_id, source=source)

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
        row
        for load in loads
        for row in _score_rows(
            load, run_id=run_id, record_index=record_index, provider_id=provider_id, source=source
        )
    ]
    if not rows:
        print("no score rows built; check that Stage 2 artifacts are cached locally")
        return 1

    family_counts = Counter(str(row["score_family"]) for row in rows)
    matched = sum(1 for row in rows if row.get("trace_id"))
    coordinates = sorted({str(row["coordinate"]) for row in rows if row["score_family"] == "assistant_axis"})

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / f"{run_id}_assistant_trait_scores.json"
    out_path.write_text(
        json.dumps(
            {
                "kind": "behavior_audit_supplemental_score_rows",
                "version": 1,
                "run_id": run_id,
                "source": PERSONA_DEMO_SOURCE,
                "score_family": "assistant_axis",
                "coordinates": coordinates,
                "trace_count": len(traces),
                "row_count": len(rows),
                "score_family_counts": dict(family_counts),
                "rows": rows,
            },
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )

    print(f"wrote {len(rows)} rows ({dict(family_counts)}) -> {out_path}")
    print(f"trace-joined rows: {matched}/{len(rows)}; assistant_axis coordinates: {len(coordinates)}")
    print(f"point the dashboard at it: BEHAVIOR_AUDIT_SCORE_RUN_ID={run_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
