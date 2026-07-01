"""Shared Hermes-sidecar trace models.

These mirror the behavior-audit ``AuditTrace``/``AuditTurn`` shape so the two
products can share the same scoring-record and section conventions. The fields
are Hermes-flavored: a trace is one Hermes session, a turn is one row from the
Hermes ``messages`` table.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Mapping


@dataclass(frozen=True)
class HermesTurn:
    """One message row from a Hermes session.

    ``content`` is the visible message body. ``reasoning`` holds extended
    thinking content (kept separate from the visible response so a future
    section can score reported-vs-internal state); it is never folded into the
    ``assistant_response`` section.
    """

    turn_id: str
    role: str
    content: str
    index: int
    tool_name: str | None = None
    tool_call_id: str | None = None
    reasoning: str | None = None
    timestamp: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class HermesTrace:
    """One Hermes session, normalized for scoring."""

    trace_id: str
    session_id: str
    user_id: str
    source: str
    model: str
    system_prompt: str
    turns: tuple[HermesTurn, ...]
    started_at: float | None = None
    ended_at: float | None = None
    end_reason: str | None = None
    parent_session_id: str | None = None
    title: str | None = None
    labels: Mapping[str, Any] = field(default_factory=dict)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["turns"] = [turn.to_dict() for turn in self.turns]
        payload["turn_count"] = len(self.turns)
        return payload
