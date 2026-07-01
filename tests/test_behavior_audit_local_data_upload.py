from __future__ import annotations

from backend.api.tau2_loader import smoke_traces
from backend.scripts.upload_local_data_to_neon import (
    load_score_summary_payloads,
    load_supplemental_score_payloads,
    trace_table_rows,
)


def test_trace_table_rows_normalize_traces_and_turns() -> None:
    traces = smoke_traces()[:1]
    trace_rows, turn_rows = trace_table_rows(traces, provider_id="tau2_smoke", source="fixture")

    assert trace_rows == [
        {
            "provider_id": "tau2_smoke",
            "trace_id": traces[0].trace_id,
            "session_id": traces[0].session_id,
            "user_id": traces[0].user_id,
            "domain": traces[0].domain,
            "task_id": traces[0].task_id,
            "outcome": traces[0].outcome,
            "reward": traces[0].reward,
            "source_model": traces[0].source_model,
            "user_model": traces[0].user_model,
            "turn_count": len(traces[0].turns),
            "labels": dict(traces[0].labels),
            "metadata": dict(traces[0].metadata),
            "source": "fixture",
        }
    ]
    assert len(turn_rows) == len(traces[0].turns)
    assert {"provider_id", "trace_id", "turn_id", "turn_index", "role", "content", "tool_name"}.issubset(turn_rows[0])


def test_local_behavior_audit_payloads_are_loadable() -> None:
    supplemental = load_supplemental_score_payloads()
    summaries = load_score_summary_payloads()

    assert supplemental
    assert summaries
    assert supplemental[0]["rows"]
    assert {"run_id", "artifact_id", "score_family", "coordinate", "example_key", "score", "row_payload"}.issubset(
        supplemental[0]["rows"][0]
    )
    assert {"run_id", "score_inventory", "score_surface", "module_scores"}.issubset(summaries[0])
