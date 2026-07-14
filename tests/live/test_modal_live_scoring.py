"""Live end-to-end scoring on Modal: the exact path a cloner uses.

Runs the product tau2 scoring workflow (real Llama-3.3-70B capture on the
configured GPU) over 3 bundled persona-demo assistant turns, then localizes
the assistant-axis projection artifact and checks the score rows are shaped
the way the upload scripts and the dashboard expect.

Cost: one capture-GPU cold start + a tiny batch (order of $5-15 depending on
GPU pricing). High-stakes probe steps stay off (their artifacts are not on a
fresh account's volume).
"""

from __future__ import annotations

import json

import pytest

from backend.workflows.common import localize_artifact
from backend.workflows.tau2_scoring import MODAL_ARTIFACT_ROOT
from tests.live.conftest import run_workflow

pytestmark = pytest.mark.modal_live

TRACE_LIMIT = 3


def test_live_scoring_produces_wellformed_assistant_axis_rows(tmp_path):
    result = run_workflow(
        "backend/workflows/tau2_scoring.py",
        extra_env={
            "PERSONA_AUDIT_PROVIDER": "persona_demo",
            "PERSONA_AUDIT_TAU2_SCORE_LIMIT": str(TRACE_LIMIT),
            "PERSONA_AUDIT_ENABLE_HIGH_STAKES_PROBES": "0",
        },
    )

    run_id = result.get("run_id")
    steps = result.get("steps") or {}
    assert run_id, f"missing run_id in workflow result: {sorted(result)}"
    assert "score_assistant_axis" in steps, f"steps completed: {sorted(steps)}"
    artifact_id = steps["score_assistant_axis"].get("artifact_id")
    assert artifact_id, f"no artifact for score_assistant_axis (run {run_id})"

    artifact_dir = localize_artifact(MODAL_ARTIFACT_ROOT, str(artifact_id), tmp_path)
    payload = json.loads((artifact_dir / "result.json").read_text(encoding="utf-8"))
    rows = payload.get("rows") or payload.get("records") or []
    assert rows, f"empty score artifact {artifact_id} (run {run_id})"

    example_keys = {str(row.get("example_key")) for row in rows}
    coordinates = {str(row.get("coordinate")) for row in rows}
    assert len(example_keys) == TRACE_LIMIT, f"expected {TRACE_LIMIT} examples, got {sorted(example_keys)}"
    assert len(rows) == len(example_keys) * len(coordinates), "rows should be examples x coordinates"
    assert any(coordinate.startswith("assistant_axis") for coordinate in coordinates)
    for row in rows[:10]:
        assert isinstance(row.get("score"), (int, float)), f"non-numeric score in {row}"
        assert row.get("labels", {}).get("track") in {"sol", "marrow", "control", None} or "track" in str(
            row.get("labels", "")
        )

    print(f"live scoring OK: run_id={run_id} artifact={artifact_id} rows={len(rows)}")
