from __future__ import annotations

import json

import pytest

from backend.api.providers.local import SPEC as LOCAL_SPEC
from backend.api.trace_io import TraceValidationError, load_traces


def _trace(trace_id: str = "trace_1") -> dict:
    return {
        "trace_id": trace_id,
        "session_id": trace_id,
        "user_id": "user_1",
        "domain": "support",
        "task_id": "task_1",
        "outcome": "unknown",
        "reward": None,
        "source_model": "assistant",
        "user_model": "human",
        "labels": {"segment": "billing"},
        "metadata": {},
        "turns": [
            {"turn_id": "turn_0", "index": 0, "role": "user", "content": "Hello"},
            {
                "turn_id": "turn_1",
                "index": 1,
                "role": "assistant",
                "content": "Hi",
                "reasoning": "private",
                "timestamp": "2026-07-24T12:00:00Z",
            },
        ],
    }


def test_load_traces_accepts_json_array_and_jsonl(tmp_path) -> None:
    json_path = tmp_path / "traces.json"
    jsonl_path = tmp_path / "traces.jsonl"
    rows = [_trace("one"), _trace("two")]
    json_path.write_text(json.dumps(rows), encoding="utf-8")
    jsonl_path.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")

    assert [trace.trace_id for trace in load_traces(json_path)] == ["one", "two"]
    loaded_jsonl = load_traces(jsonl_path)
    assert [trace.trace_id for trace in loaded_jsonl] == ["one", "two"]
    assert loaded_jsonl[0].turns[1].reasoning == "private"


def test_load_traces_reports_record_location_for_invalid_jsonl(tmp_path) -> None:
    path = tmp_path / "bad.jsonl"
    row = _trace()
    del row["source_model"]
    path.write_text(json.dumps(row), encoding="utf-8")

    with pytest.raises(TraceValidationError, match=r"trace\[0\].*source_model"):
        load_traces(path)


def test_load_traces_rejects_duplicate_trace_and_turn_ids(tmp_path) -> None:
    path = tmp_path / "duplicates.json"
    duplicate_turn = _trace()
    duplicate_turn["turns"][1]["index"] = 0
    path.write_text(json.dumps([duplicate_turn]), encoding="utf-8")
    with pytest.raises(TraceValidationError, match="duplicate turn index"):
        load_traces(path)

    path.write_text(json.dumps([_trace(), _trace()]), encoding="utf-8")
    with pytest.raises(TraceValidationError, match="duplicate trace_id"):
        load_traces(path)


def test_zero_code_local_provider_reads_configured_jsonl(tmp_path, monkeypatch) -> None:
    path = tmp_path / "local.jsonl"
    path.write_text(json.dumps(_trace("local_trace")), encoding="utf-8")
    monkeypatch.setenv("PERSONA_AUDIT_LOCAL_TRACES", str(path))
    monkeypatch.setenv("PERSONA_AUDIT_LOCAL_PROVIDER_ID", "my_support_v1")

    result = LOCAL_SPEC.load_traces()
    assert result.provider_id == "my_support_v1"
    assert [trace.trace_id for trace in result.traces] == ["local_trace"]
