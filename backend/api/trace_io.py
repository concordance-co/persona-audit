"""Serialize/deserialize normalized ``AuditTrace`` JSON files.

This is the on-disk form of the adapter contract (docs/adapter-contract.md):
a JSON array of trace objects, each with a ``turns`` array. The bundled
persona-demo dataset (``data/demo/normalized_traces.json``) is the reference
example. Pure JSON <-> dataclass mapping; no provider or scoring logic here.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path

from backend.api.models import AuditTrace, AuditTurn


def save_traces(traces: Sequence[AuditTrace], path: str | Path) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps([trace.to_dict() for trace in traces], indent=2, sort_keys=True),
        encoding="utf-8",
    )


def load_traces(path: str | Path) -> list[AuditTrace]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    traces: list[AuditTrace] = []
    for row in payload:
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
                trace_id=str(row["trace_id"]),
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
