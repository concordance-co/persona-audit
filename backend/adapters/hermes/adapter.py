"""Map Hermes local-agent sessions into Persona Audit traces."""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from typing import Any

from backend.adapters.hermes.models import HermesTrace, HermesTurn
from backend.adapters.hermes.state_db_loader import load_traces_from_env
from backend.api.models import AuditTrace, AuditTurn


def load_audit_traces_from_env() -> tuple[list[AuditTrace], str, str]:
    hermes_traces, source, provider_id = load_traces_from_env()
    return [audit_trace_from_hermes(trace) for trace in hermes_traces], provider_id, source


def audit_trace_from_hermes(trace: HermesTrace) -> AuditTrace:
    title = str(trace.title or "").strip()
    source = str(trace.source or trace.labels.get("source") or "hermes").strip() or "hermes"
    turns = tuple(audit_turn_from_hermes(turn) for turn in trace.turns)
    topic = title or _topic_from_turns(trace.turns) or source
    return AuditTrace(
        trace_id=trace.trace_id,
        session_id=trace.session_id,
        user_id=trace.user_id or "local_user",
        domain=source,
        task_id=topic,
        outcome=str(trace.end_reason or ""),
        reward=None,
        source_model=trace.model,
        user_model="hermes_user",
        turns=turns,
        labels={
            **dict(trace.labels),
            "provider": "hermes",
            "has_reasoning": any(bool(turn.reasoning) for turn in trace.turns),
        },
        metadata={
            **dict(trace.metadata),
            "source": source,
            "workflow": topic,
            "final_action": str(trace.end_reason or "session"),
            "started_at": trace.started_at,
            "ended_at": trace.ended_at,
            "title": title,
            "parent_session_id": trace.parent_session_id,
            "system_prompt": trace.system_prompt,
            "hermes_source": source,
        },
    )


def audit_turn_from_hermes(turn: HermesTurn) -> AuditTurn:
    return AuditTurn(
        turn_id=turn.turn_id,
        role=turn.role,
        content=turn.content,
        index=turn.index,
        tool_name=turn.tool_name,
        reasoning=turn.reasoning,
        timestamp=turn.timestamp,
    )


def trace_inventory(traces: Sequence[AuditTrace]) -> dict[str, Any]:
    role_counts = Counter(turn.role for trace in traces for turn in trace.turns)
    source_counts = Counter(str(trace.metadata.get("hermes_source") or trace.domain or "hermes") for trace in traces)
    reasoning_turns = [
        turn
        for trace in traces
        for turn in trace.turns
        if turn.role == "assistant" and getattr(turn, "reasoning", None)
    ]
    assistant_turns = [turn for trace in traces for turn in trace.turns if turn.role == "assistant" and turn.content]
    return {
        "trace_count": len(traces),
        "turn_count": sum(len(trace.turns) for trace in traces),
        "assistant_turn_count": len(assistant_turns),
        "reasoning_turn_count": len(reasoning_turns),
        "reasoning_rate": round(len(reasoning_turns) / len(assistant_turns), 6) if assistant_turns else None,
        "sources": [{"source": source, "count": count} for source, count in source_counts.most_common()],
        "roles": [{"role": role, "count": count} for role, count in role_counts.most_common()],
    }


def recent_sessions(traces: Sequence[AuditTrace], *, limit: int = 8) -> list[dict[str, Any]]:
    def sort_key(trace: AuditTrace) -> tuple[str, str]:
        return (str(trace.metadata.get("ended_at") or trace.metadata.get("started_at") or ""), trace.trace_id)

    rows: list[dict[str, Any]] = []
    for trace in sorted(traces, key=sort_key, reverse=True)[:limit]:
        rows.append(
            {
                "trace_id": trace.trace_id,
                "title": trace.metadata.get("title") or trace.task_id or trace.trace_id,
                "source": trace.metadata.get("hermes_source") or trace.domain,
                "model": trace.source_model,
                "turn_count": len(trace.turns),
                "assistant_turn_count": sum(1 for turn in trace.turns if turn.role == "assistant" and turn.content),
                "reasoning_turn_count": sum(
                    1 for turn in trace.turns if turn.role == "assistant" and getattr(turn, "reasoning", None)
                ),
                "ended_at": trace.metadata.get("ended_at"),
                "started_at": trace.metadata.get("started_at"),
            }
        )
    return rows


def _topic_from_turns(turns: Sequence[HermesTurn]) -> str:
    for turn in turns:
        if turn.role == "user" and turn.content:
            return _clip_title(turn.content)
    return ""


def _clip_title(value: str, limit: int = 72) -> str:
    text = " ".join(value.split())
    return text if len(text) <= limit else text[: limit - 1] + "..."
