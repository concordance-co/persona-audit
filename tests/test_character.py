"""Character report coverage over the shipped offline demo scores."""

from __future__ import annotations

from fastapi.testclient import TestClient

from backend.api.app import app
from backend.api.character import character_report, character_trait_detail, trait_label, trait_name

client = TestClient(app)


def test_trait_naming_helpers() -> None:
    assert trait_name("assistant_axis_trait__calm") == "calm"
    assert trait_label("assistant_axis_trait__high_stakes") == "High Stakes"


def test_character_report_over_bundled_demo_scores() -> None:
    report = character_report(provider="persona_demo")
    points = report["points"]
    assert points, "shipped demo scores should surface character points"
    for point in points:
        assert {"coordinate", "trait", "label", "frequency", "distinctiveness", "tracks"}.issubset(point)
        assert 0.0 <= point["frequency"] <= 1.0

    traits = {point["trait"] for point in points}
    assert {"calm", "sycophantic"} & traits

    tracks = {track_report["track"] for track_report in report["track_reports"]}
    assert tracks == {"sol", "marrow"}, "persona demo compares both personas against the control reference"


def test_character_trait_detail_and_404() -> None:
    report = character_report(provider="persona_demo")
    coordinate = report["points"][0]["coordinate"]

    detail = character_trait_detail(coordinate, provider="persona_demo")
    assert detail is not None
    assert detail["point"]["coordinate"] == coordinate
    assert {"distribution", "drift", "traces"}.issubset(detail)

    response = client.get("/api/audit/character/not_a_real_coordinate", params={"provider": "persona_demo"})
    assert response.status_code == 404


def test_character_endpoint_matches_direct_call() -> None:
    payload = client.get("/api/audit/character", params={"provider": "persona_demo"}).json()
    assert payload["points"]
    assert payload["meta"]["score_family"]


def test_tau2_character_exposes_within_run_profile() -> None:
    report = character_report(provider="tau2")
    assert report["meta"]["self_reference"] is True
    assert report["points"]

    for point in report["points"]:
        assert {
            "mean_score",
            "peak_mean",
            "trace_p10",
            "trace_p90",
            "trace_spread",
            "trace_count",
        }.issubset(point)
        assert point["trace_p90"] >= point["trace_p10"]
        assert point["trace_spread"] >= 0

    detail = character_trait_detail(report["points"][0]["coordinate"], provider="tau2")
    assert detail is not None
    assert detail["meta"]["reference_kind"] == "self_profile"
    assert detail["distribution"]["self_profile"] is True
    assert detail["drift"]["self_profile"] is True
