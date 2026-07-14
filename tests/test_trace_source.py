from __future__ import annotations

from backend.api import trace_source


def test_traces_from_neon_rows_reconstructs_audit_traces() -> None:
    traces = trace_source.traces_from_neon_rows(
        [
            {
                "provider_id": "tau2_public_airline",
                "trace_id": "trace_1",
                "session_id": "session_1",
                "user_id": "user_1",
                "domain": "airline",
                "task_id": "task_1",
                "outcome": "pass",
                "reward": 1,
                "source_model": "agent_model",
                "user_model": "user_model",
                "labels": {"is_high_stakes_candidate": True},
                "metadata": {"source": "tau2"},
            }
        ],
        [
            {
                "provider_id": "tau2_public_airline",
                "trace_id": "trace_1",
                "turn_id": "turn_001",
                "turn_index": 1,
                "role": "assistant",
                "content": "Done.",
                "tool_name": None,
            },
            {
                "provider_id": "tau2_public_airline",
                "trace_id": "trace_1",
                "turn_id": "turn_000",
                "turn_index": 0,
                "role": "user",
                "content": "Help me.",
                "tool_name": None,
            },
        ],
    )

    assert len(traces) == 1
    trace = traces[0]
    assert trace.trace_id == "trace_1"
    assert trace.reward == 1.0
    assert trace.labels == {"is_high_stakes_candidate": True}
    assert [turn.role for turn in trace.turns] == ["user", "assistant"]
    assert [turn.content for turn in trace.turns] == ["Help me.", "Done."]


def test_preferred_neon_provider_id_uses_canonical_provider_when_available(monkeypatch) -> None:
    from backend.api.registry import get_provider

    monkeypatch.setenv("PERSONA_AUDIT_TAU2_PROVIDER", "tau2_public_airline")
    spec = get_provider("tau2")

    assert (
        trace_source._preferred_neon_provider_id(spec, ["tau2_other", "tau2_public_airline"]) == "tau2_public_airline"
    )
    assert trace_source._preferred_neon_provider_id(spec, ["tau2_other"]) == "tau2_other"
