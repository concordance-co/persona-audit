"""Live end-to-end generation on Modal: the factory's smoke round.

Runs factory/workflows/demo_generation.py with its smoke default (1 seed x 3
persona tracks, turn 0) on the configured generation GPU, then localizes the
round artifact and checks one non-empty generation per track came back.

Cost: one generation-GPU cold start + 3 short generations (order of $5-10).
"""

from __future__ import annotations

import json

import pytest

from backend.workflows.common import localize_artifact
from factory.workflows.demo_generation import MODAL_ARTIFACT_ROOT
from tests.live.conftest import run_workflow

pytestmark = pytest.mark.modal_live


def test_live_generation_answers_every_track(tmp_path):
    result = run_workflow("factory/workflows/demo_generation.py")

    run_id = result.get("run_id")
    steps = result.get("steps") or {}
    assert "generate_round" in steps, f"steps completed: {sorted(steps)} (run {run_id})"
    artifact_id = steps["generate_round"].get("artifact_id")
    assert artifact_id, f"no artifact for generate_round (run {run_id})"

    artifact_dir = localize_artifact(MODAL_ARTIFACT_ROOT, str(artifact_id), tmp_path)
    payload = json.loads((artifact_dir / "result.json").read_text(encoding="utf-8"))
    rows = payload.get("rows") or payload.get("records") or []
    assert len(rows) == 3, f"smoke round should generate one reply per track, got {len(rows)} (run {run_id})"

    # Rows identify by example_key ("demo_<seed>_<track>_t<NN>") — the same
    # contract the factory driver uses to fold results back into histories
    # (factory/hillclimb/rounds.py:apply_round_results).
    tracks = set()
    for row in rows:
        key = str(row.get("example_key") or "")
        assert key.startswith("demo_"), f"unexpected example_key {key!r} (run {run_id})"
        tracks.add(key.rsplit("_", 2)[-2])
        text = str(row.get("generated_text") or "").strip()
        assert text, f"empty generation for {key} (run {run_id})"
    assert tracks == {"sol", "marrow", "control"}, f"tracks generated: {sorted(tracks)}"

    print(f"live generation OK: run_id={run_id} artifact={artifact_id}")
