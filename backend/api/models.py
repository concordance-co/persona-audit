"""Shared behavior-audit trace models."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Mapping


@dataclass(frozen=True)
class AuditTurn:
    turn_id: str
    role: str
    content: str
    index: int
    tool_name: str | None = None
    reasoning: str | None = None
    timestamp: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class AuditTrace:
    trace_id: str
    session_id: str
    user_id: str
    domain: str
    task_id: str
    outcome: str
    reward: float | None
    source_model: str
    user_model: str
    turns: tuple[AuditTurn, ...]
    labels: Mapping[str, Any] = field(default_factory=dict)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["turns"] = [turn.to_dict() for turn in self.turns]
        payload["turn_count"] = len(self.turns)
        return payload
