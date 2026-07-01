from __future__ import annotations

from fastapi.testclient import TestClient

from backend.api.app import app
from backend.api.character import _distribution_shift, _drift_curve, compute_character


client = TestClient(app)

TRAIT = "assistant_axis_trait__sycophantic"
OTHER = "assistant_axis_trait__hostile"


def _row(coordinate: str, trace_id: str, score: float, turn_index: int = 0) -> dict:
    return {"coordinate": coordinate, "trace_id": trace_id, "score": score, "turn_index": turn_index}


def _point(result: dict, coordinate: str) -> dict | None:
    return next((p for p in result["points"] if p["coordinate"] == coordinate), None)
