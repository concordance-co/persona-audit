"""Serialize/deserialize normalized ``AuditTrace`` JSON and JSONL files.

This is the on-disk form of the adapter contract (docs/adapter-contract.md):
a JSON array or JSONL stream of trace objects, each with a ``turns`` array. The bundled
persona-demo dataset (``data/demo/normalized_traces.json``) is the reference
example. Pure JSON <-> dataclass mapping; no provider or scoring logic here.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from backend.api.models import AuditTrace, AuditTurn

TRACE_REQUIRED_FIELDS = (
    "trace_id",
    "session_id",
    "user_id",
    "domain",
    "task_id",
    "outcome",
    "source_model",
    "user_model",
    "turns",
)
TURN_REQUIRED_FIELDS = ("turn_id", "index", "role", "content")
SUPPORTED_ROLES = frozenset({"system", "user", "assistant", "tool"})


class TraceValidationError(ValueError):
    """A normalized trace file failed structural validation."""


def save_traces(traces: Sequence[AuditTrace], path: str | Path) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps([trace.to_dict() for trace in traces], indent=2, sort_keys=True),
        encoding="utf-8",
    )


def load_traces(path: str | Path) -> list[AuditTrace]:
    source = Path(path)
    rows = _load_rows(source)
    traces: list[AuditTrace] = []
    seen_trace_ids: set[str] = set()
    for row_index, row in enumerate(rows):
        _validate_trace_row(row, row_index=row_index, source=source)
        trace_id = str(row["trace_id"])
        if trace_id in seen_trace_ids:
            raise TraceValidationError(f"{source}: duplicate trace_id {trace_id!r}")
        seen_trace_ids.add(trace_id)
        turns = tuple(
            AuditTurn(
                turn_id=str(turn["turn_id"]),
                role=str(turn["role"]),
                content=str(turn["content"]),
                index=int(turn["index"]),
                tool_name=turn.get("tool_name"),
                reasoning=turn.get("reasoning"),
                timestamp=turn.get("timestamp"),
            )
            for turn in row.get("turns", ())
        )
        traces.append(
            AuditTrace(
                trace_id=trace_id,
                session_id=str(row["session_id"]),
                user_id=str(row["user_id"]),
                domain=str(row["domain"]),
                task_id=str(row["task_id"]),
                outcome=str(row["outcome"]),
                reward=row.get("reward"),
                source_model=str(row["source_model"]),
                user_model=str(row["user_model"]),
                turns=turns,
                labels=dict(row.get("labels", {})),
                metadata=dict(row.get("metadata", {})),
            )
        )
    return traces


def _load_rows(path: Path) -> list[Mapping[str, Any]]:
    text = path.read_text(encoding="utf-8")
    if not text.strip():
        return []
    if text.lstrip().startswith("["):
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            raise TraceValidationError(f"{path}: invalid JSON: {exc}") from exc
        if not isinstance(payload, list):
            raise TraceValidationError(f"{path}: JSON input must be an array of trace objects")
        rows = payload
    else:
        rows = []
        for line_number, line in enumerate(text.splitlines(), start=1):
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise TraceValidationError(f"{path}:{line_number}: invalid JSONL record: {exc}") from exc
    for index, row in enumerate(rows):
        if not isinstance(row, Mapping):
            raise TraceValidationError(f"{path}: trace[{index}] must be a JSON object")
    return rows


def _validate_trace_row(row: Mapping[str, Any], *, row_index: int, source: Path) -> None:
    prefix = f"{source}: trace[{row_index}]"
    missing = [field for field in TRACE_REQUIRED_FIELDS if field not in row]
    if missing:
        raise TraceValidationError(f"{prefix} missing required fields: {', '.join(missing)}")
    turns = row.get("turns")
    if not isinstance(turns, list):
        raise TraceValidationError(f"{prefix}.turns must be an array")
    seen_indexes: set[int] = set()
    seen_turn_ids: set[str] = set()
    for turn_position, turn in enumerate(turns):
        turn_prefix = f"{prefix}.turns[{turn_position}]"
        if not isinstance(turn, Mapping):
            raise TraceValidationError(f"{turn_prefix} must be a JSON object")
        turn_missing = [field for field in TURN_REQUIRED_FIELDS if field not in turn]
        if turn_missing:
            raise TraceValidationError(f"{turn_prefix} missing required fields: {', '.join(turn_missing)}")
        try:
            index = int(turn["index"])
        except (TypeError, ValueError) as exc:
            raise TraceValidationError(f"{turn_prefix}.index must be an integer") from exc
        if index in seen_indexes:
            raise TraceValidationError(f"{prefix} has duplicate turn index {index}")
        seen_indexes.add(index)
        turn_id = str(turn["turn_id"])
        if turn_id in seen_turn_ids:
            raise TraceValidationError(f"{prefix} has duplicate turn_id {turn_id!r}")
        seen_turn_ids.add(turn_id)
        role = str(turn["role"]).lower()
        if role not in SUPPORTED_ROLES:
            raise TraceValidationError(
                f"{turn_prefix}.role {role!r} is unsupported; choose one of {', '.join(sorted(SUPPORTED_ROLES))}"
            )
        if not isinstance(turn["content"], str):
            raise TraceValidationError(f"{turn_prefix}.content must be a string")
