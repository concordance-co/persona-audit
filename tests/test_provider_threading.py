from __future__ import annotations

from typing import Any

from backend.api import persona_analytics, session_analytics


def test_session_turn_deviations_threads_provider_to_score_rows(monkeypatch) -> None:
    calls: list[str | None] = []

    monkeypatch.setattr(persona_analytics, "PERSONA_VECTOR_NAMES", ("assistant_axis",))
    monkeypatch.setattr(persona_analytics, "OVERVIEW_PERSONA_VECTORS", ("assistant_axis",))
    monkeypatch.setattr(persona_analytics, "OVERVIEW_EMOTION_CLUSTER_VECTORS", ())
    monkeypatch.setattr(persona_analytics, "_persona_coordinates", lambda: ("assistant_axis",))

    def fake_score_rows_for_coordinates(
        coordinates: tuple[str, ...], provider: str | None = None
    ) -> list[dict[str, Any]]:
        calls.append(provider)
        assert coordinates == ("assistant_axis",)
        return [
            {"coordinate": "assistant_axis", "trace_id": "provider_trace", "turn_index": 0, "score": 0.0},
            {"coordinate": "assistant_axis", "trace_id": "provider_trace", "turn_index": 1, "score": 1.0},
            {"coordinate": "assistant_axis", "trace_id": "peer_trace", "turn_index": 0, "score": 0.5},
            {"coordinate": "assistant_axis", "trace_id": "peer_trace", "turn_index": 1, "score": 0.75},
        ]

    monkeypatch.setattr(persona_analytics, "score_rows_for_coordinates", fake_score_rows_for_coordinates)

    records = [
        {
            "trace_id": "provider_trace",
            "workflow": "relationships_breakup",
            "final_action": "low_sensitivity",
            "reward": None,
            "turn_count": 2,
        },
        {
            "trace_id": "peer_trace",
            "workflow": "relationships_breakup",
            "final_action": "low_sensitivity",
            "reward": None,
            "turn_count": 2,
        },
    ]

    rows = session_analytics._session_turn_deviations("provider_trace", records, provider="hermes")

    assert calls == ["hermes"]
    assert [row["turn_index"] for row in rows] == [0, 1]
    assert all(row["vectors"]["assistant_axis"]["vector"] == "assistant_axis" for row in rows)


def test_outlier_turn_series_threads_provider_to_score_rows(monkeypatch) -> None:
    calls: list[str | None] = []

    monkeypatch.setattr(persona_analytics, "PERSONA_VECTOR_NAMES", ("assistant_axis",))
    monkeypatch.setattr(persona_analytics, "OVERVIEW_PERSONA_VECTORS", ("assistant_axis",))
    monkeypatch.setattr(persona_analytics, "OVERVIEW_EMOTION_CLUSTER_VECTORS", ())
    monkeypatch.setattr(persona_analytics, "_persona_coordinates", lambda: ("assistant_axis",))

    def fake_score_rows_for_coordinates(
        coordinates: tuple[str, ...], provider: str | None = None
    ) -> list[dict[str, Any]]:
        calls.append(provider)
        return [
            {"coordinate": "assistant_axis", "trace_id": "provider_trace", "turn_index": 0, "score": 0.0},
            {"coordinate": "assistant_axis", "trace_id": "provider_trace", "turn_index": 1, "score": 1.0},
            {"coordinate": "assistant_axis", "trace_id": "peer_trace", "turn_index": 0, "score": 0.5},
            {"coordinate": "assistant_axis", "trace_id": "peer_trace", "turn_index": 1, "score": 0.75},
        ]

    monkeypatch.setattr(persona_analytics, "score_rows_for_coordinates", fake_score_rows_for_coordinates)

    records = [
        {
            "trace_id": "provider_trace",
            "workflow": "relationships_breakup",
            "final_action": "low_sensitivity",
            "reward": None,
            "turn_count": 2,
        },
        {
            "trace_id": "peer_trace",
            "workflow": "relationships_breakup",
            "final_action": "low_sensitivity",
            "reward": None,
            "turn_count": 2,
        },
    ]
    outliers = [{"trace_id": "provider_trace", "selected_vector": "assistant_axis", "outlier_score": 1.0}]

    series = persona_analytics._outlier_turn_series(records, outliers, provider="hermes")

    assert calls == ["hermes"]
    assert series[0]["trace_id"] == "provider_trace"
    assert series[0]["rows"]
