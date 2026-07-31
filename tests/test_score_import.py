from __future__ import annotations

import gzip
import json
import sys

from backend.api.registry import TraceLoadResult
from backend.api.tau2_loader import smoke_traces
from backend.scripts import upload_tau2_scores


def test_score_import_can_materialize_local_cache_without_database(tmp_path, monkeypatch, capsys) -> None:
    trace = smoke_traces()[0]
    example_key = f"{trace.trace_id}__assistant_000"
    payloads = {
        "projection_test": {
            "kind": "projection",
            "rows": [
                {
                    "example_key": example_key,
                    "coordinate": "assistant_axis_trait__calm",
                    "layer": 40,
                    "score": 0.5,
                }
            ],
        },
        "emotion_test": {
            "kind": "emotion_score",
            "rows": [
                {
                    "example_key": example_key,
                    "coordinate": "relief",
                    "layer": 52,
                    "score": 0.25,
                }
            ],
        },
    }
    monkeypatch.setattr(
        upload_tau2_scores,
        "load_product_traces",
        lambda _provider: TraceLoadResult([trace], "local", "local fixture"),
    )
    monkeypatch.setattr(upload_tau2_scores, "ModalVolumeStore", lambda **_kwargs: object())
    monkeypatch.setattr(upload_tau2_scores, "load_result", lambda _store, artifact_id: payloads[artifact_id])

    def fail_database_lookup(_env: str) -> None:
        raise AssertionError("database lookup should be skipped")

    monkeypatch.setattr(upload_tau2_scores, "configured_database_url", fail_database_lookup)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "upload_tau2_scores",
            "--provider",
            "local",
            "--run-id",
            "wr_local_test",
            "--capture-artifact-id",
            "capture_test",
            "--projection-artifact-id",
            "projection_test",
            "--emotion-artifact-id",
            "emotion_test",
            "--artifact-root",
            "/data/artifacts/persona_audit_local_scoring_v1",
            "--local-cache-dir",
            str(tmp_path),
            "--no-high-stakes",
            "--skip-database",
        ],
    )

    upload_tau2_scores.main()

    path = tmp_path / "wr_local_test_assistant_trait_scores.json.gz"
    payload = json.loads(gzip.decompress(path.read_bytes()))
    assert payload["kind"] == "persona_audit_supplemental_score_rows"
    assert payload["score_family_counts"] == {"assistant_axis": 1, "emotion": 1}
    assert {row["trace_id"] for row in payload["rows"]} == {trace.trace_id}
    output = capsys.readouterr().out
    assert "PERSONA_AUDIT_LOCAL_SCORE_RUN_ID=wr_local_test" in output
    assert "local cache" in output
