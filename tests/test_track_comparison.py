"""Track comparison: direct persona-vs-persona contrast for the demo dataset.

The persona demo Overview compares tracks against each other (control as the
reference, paired by seed), never against the pooled all-track baseline. These
tests pin that contract at the builder level and through the API payload.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from backend.api import persona_analytics
from backend.api.app import app

client = TestClient(app)


def _record(track: str, seed: str, oriented: float, display: float) -> dict:
    return {
        "trace_id": f"{track}_{seed}",
        "task_id": seed,
        "final_action": track,
        "workflow": "decision",
        "assistant_axis": display,
        "assistant_axis_raw": oriented,
        "assistant_axis_oriented": oriented,
    }


def test_track_comparison_contrasts_tracks_directly(monkeypatch) -> None:
    monkeypatch.setattr(persona_analytics, "PERSONA_VECTOR_NAMES", ("assistant_axis",))
    records = []
    for index, seed in enumerate(("s1", "s2", "s3")):
        records.append(_record("sol", seed, 1.0 + index * 0.02, 0.9))
        records.append(_record("marrow", seed, -1.0 - index * 0.02, 0.1))
        records.append(_record("control", seed, 0.0 + index * 0.01, 0.5))

    result = persona_analytics._track_comparison(records)

    assert result["available"] is True
    assert [row["track"] for row in result["tracks"]] == ["sol", "marrow", "control"]
    assert all(row["n"] == 3 for row in result["tracks"])
    assert result["paired_task_count"] == 3

    vector = result["vectors"][0]
    assert vector["vector"] == "assistant_axis"
    assert vector["eta_squared"] > 0.9
    assert {row["track"] for row in vector["tracks"]} == {"sol", "marrow", "control"}

    contrasts = {(row["a"], row["b"]): row for row in vector["contrasts"]}
    assert set(contrasts) == {("sol", "control"), ("marrow", "control"), ("sol", "marrow")}
    sol = contrasts[("sol", "control")]
    assert sol["n_pairs"] == 3
    assert (sol["wins"], sol["losses"], sol["ties"]) == (3, 0, 0)
    assert sol["mean_delta"] > 0
    assert sol["paired_d"] > 0
    marrow = contrasts[("marrow", "control")]
    assert (marrow["wins"], marrow["losses"]) == (0, 3)
    assert marrow["mean_delta"] < 0


def test_track_comparison_requires_control_group(monkeypatch) -> None:
    monkeypatch.setattr(persona_analytics, "PERSONA_VECTOR_NAMES", ("assistant_axis",))
    records = [_record("sol", "s1", 1.0, 0.9), _record("marrow", "s1", -1.0, 0.1)]
    assert persona_analytics._track_comparison(records) == {"available": False}


def test_persona_demo_api_payload_carries_track_comparison() -> None:
    response = client.get("/api/audit/product-analytics", params={"provider": "persona_demo"})
    assert response.status_code == 200
    persona = response.json()["persona_overview"]
    assert persona["available"] is True

    comparison = persona["track_comparison"]
    assert comparison["available"] is True
    assert [row["track"] for row in comparison["tracks"]] == ["sol", "marrow", "control"]
    assert comparison["paired_task_count"] == 25

    etas = [row["eta_squared"] for row in comparison["vectors"]]
    assert etas == sorted(etas, reverse=True)

    top = comparison["vectors"][0]
    pairs = {(row["a"], row["b"]) for row in top["contrasts"]}
    assert pairs == {("sol", "control"), ("marrow", "control"), ("sol", "marrow")}
    for contrast in top["contrasts"]:
        assert contrast["n_pairs"] == 25
        assert contrast["wins"] + contrast["losses"] + contrast["ties"] == 25


def test_persona_demo_character_uses_control_as_reference() -> None:
    response = client.get("/api/audit/character", params={"provider": "persona_demo"})
    assert response.status_code == 200
    payload = response.json()
    meta = payload["meta"]
    assert meta["tracks"] == ["sol", "marrow", "control"]
    assert meta["reference_provider"] == "control"
    assert meta["reference_kind"] == "track"

    # Per-persona portraits vs control, in raw score units — no present-rates
    # or threshold-crossing counts anywhere in the comparison.
    reports = {report["track"]: report for report in payload["track_reports"]}
    assert set(reports) == {"sol", "marrow"}
    for report in reports.values():
        assert report["points"], "each persona gets a full portrait vs control"
        for point in report["points"]:
            assert "frequency" not in point
            assert point["traces"] == 25
            assert abs(point["delta"] - (point["mean_score"] - point["control_mean_score"])) < 1e-6
            assert point["peak_mean"] >= point["mean_score"]

    # The pooled points still carry raw score magnitudes per track for the heatmap.
    for point in payload["points"]:
        tracks = point["tracks"]
        assert [row["track"] for row in tracks] == ["sol", "marrow", "control"]
        assert sum(row["traces"] for row in tracks) == point["audited_total"]
        for row in tracks:
            assert row["mean_score"] is not None
            assert row["peak_mean"] >= row["mean_score"]


def test_persona_demo_trait_detail_is_per_track_vs_control() -> None:
    response = client.get(
        "/api/audit/character/assistant_axis_trait__decisive",
        params={"provider": "persona_demo"},
    )
    assert response.status_code == 200
    detail = response.json()
    assert detail["meta"]["reference_provider"] == "control"
    assert detail["distribution"]["series"] == ["sol", "marrow", "control"]
    assert detail["drift"]["series"] == ["sol", "marrow", "control"]
    assert all(row["track"] in {"sol", "marrow"} for row in detail["traces"])
    # Ranked by raw peak over ALL audited traces — no threshold filter.
    assert detail["point"]["audited_total"] == 50
    assert "frequency" not in detail["point"]
    peaks = [row["max_score"] for row in detail["traces"]]
    assert peaks == sorted(peaks, reverse=True)


def test_persona_demo_tail_attributes_modes_to_tracks() -> None:
    response = client.get("/api/audit/tail", params={"provider": "persona_demo"})
    assert response.status_code == 200
    payload = response.json()
    meta = payload["meta"]
    assert meta["tracks"] == ["sol", "marrow", "control"]
    # Extremes are measured per track, so modes are failure shapes rather than
    # rediscovered track identity.
    assert meta["baseline"] == "per_track_self"
    assert sum(row["turns"] for row in meta["tail_composition"]) == meta["n_tail_turns"]
    assert sum(row["turns"] for row in meta["corpus_composition"]) == meta["total_turns"]
    for mode in payload["modes"]:
        assert mode["tracks"], "every mode carries a track composition"
        assert sum(row["turns"] for row in mode["tracks"]) == mode["size_turns"]
        assert abs(sum(row["share"] for row in mode["tracks"]) - 1.0) < 0.01
    if payload.get("scatter"):
        assert sum(row["turns"] for row in payload["scatter"]["tracks"]) == payload["scatter"]["size_turns"]


def test_non_demo_character_and_tail_stay_pooled() -> None:
    character = client.get("/api/audit/character").json()
    assert character["meta"]["tracks"] == []
    assert all("tracks" not in point for point in character["points"])
    tail = client.get("/api/audit/tail").json()
    assert tail["meta"]["tracks"] == []
    assert all(mode.get("tracks", []) == [] for mode in tail["modes"])


def test_non_demo_providers_keep_track_comparison_off() -> None:
    response = client.get("/api/audit/product-analytics")
    assert response.status_code == 200
    persona = response.json()["persona_overview"]
    if not persona.get("available"):
        return
    assert persona.get("track_comparison", {"available": False}) == {"available": False}
