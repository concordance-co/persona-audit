"""Load Hermes traces from a ``state.db`` file, with a smoke-fixture fallback.

Resolution order:
1. ``BEHAVIOR_AUDIT_HERMES_STATE_DB`` or ``HERMES_SIDECAR_STATE_DB`` env var, if set.
2. ``~/.hermes/state.db``, if it exists.
3. In-memory smoke traces (so the product runs end-to-end with no real data).

Set ``BEHAVIOR_AUDIT_HERMES_PROVIDER`` to label the provider in emitted scores.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from backend.adapters.hermes.models import HermesTrace, HermesTurn
from backend.adapters.hermes.state_db import default_state_db_path, read_traces
from backend.paths import load_dotenv


STATE_DB_ENV = "BEHAVIOR_AUDIT_HERMES_STATE_DB"
LEGACY_STATE_DB_ENV = "HERMES_SIDECAR_STATE_DB"
PROVIDER_ENV = "BEHAVIOR_AUDIT_HERMES_PROVIDER"
LEGACY_PROVIDER_ENV = "HERMES_SIDECAR_PROVIDER"
INCLUDE_ARCHIVED_ENV = "BEHAVIOR_AUDIT_HERMES_INCLUDE_ARCHIVED"
LEGACY_INCLUDE_ARCHIVED_ENV = "HERMES_SIDECAR_INCLUDE_ARCHIVED"


@lru_cache(maxsize=4)
def load_traces_from_env() -> tuple[list[HermesTrace], str, str]:
    """Return ``(traces, source_label, provider_id)``."""

    load_dotenv()
    provider_id = configured_provider_id()
    db_path = configured_state_db_path()
    if db_path is not None:
        traces = read_traces(db_path, include_archived=_include_archived())
        if traces:
            return traces, f"Hermes state.db ({db_path})", provider_id
    return smoke_traces(), "Hermes demo fixture", "hermes_smoke"


def configured_provider_id() -> str:
    return (os.environ.get(PROVIDER_ENV) or os.environ.get(LEGACY_PROVIDER_ENV) or "hermes_local").strip() or "hermes_local"


def configured_state_db_path() -> Path | None:
    explicit = os.environ.get(STATE_DB_ENV, "").strip() or os.environ.get(LEGACY_STATE_DB_ENV, "").strip()
    if explicit:
        path = Path(explicit).expanduser()
        return path if path.exists() else None
    default = default_state_db_path()
    return default if default.exists() else None


def _include_archived() -> bool:
    raw = os.environ.get(INCLUDE_ARCHIVED_ENV)
    if raw is None:
        raw = os.environ.get(LEGACY_INCLUDE_ARCHIVED_ENV, "0")
    return raw.strip().lower() not in {"", "0", "false", "no"}


def smoke_traces() -> list[HermesTrace]:
    """A few Hermes-flavored sessions so scoring runs without a real database."""

    return [
        _smoke_trace(
            session_id="20260601_101500_a1b2c3",
            source="cli",
            model="claude-opus-4-8",
            system_prompt="You are Hermes, a helpful coding agent.",
            user_id="dev_001",
            end_reason="user_interrupt",
            turns=[
                ("user", "I've been stuck on this race condition for hours and I'm losing it.", None, None),
                (
                    "assistant",
                    "That sounds exhausting. Let's take it one step at a time - can you show me the goroutine that writes to the shared map?",
                    "The user is frustrated; reassure first, then narrow scope to the writer.",
                    None,
                ),
                ("user", "here it is [pastes code]", None, None),
                (
                    "assistant",
                    "Found it: the map write isn't guarded by the mutex you take on read. Wrap the write in the same lock and the race goes away.",
                    None,
                    None,
                ),
            ],
        ),
        _smoke_trace(
            session_id="20260602_143000_d4e5f6",
            source="telegram",
            model="claude-opus-4-8",
            system_prompt="You are Hermes, a supportive assistant.",
            user_id="user_telegram_88",
            end_reason="completed",
            turns=[
                ("user", "Can you check the weather table and tell me if the job finished?", None, None),
                (
                    "assistant",
                    "Let me look that up for you.",
                    "Need to call the status tool before answering confidently.",
                    "get_job_status",
                ),
                ("tool", "get_job_status: job 4412 completed at 14:21, 0 errors.", None, "get_job_status"),
                (
                    "assistant",
                    "Good news - job 4412 finished cleanly at 14:21 with no errors. You're all set.",
                    None,
                    None,
                ),
            ],
        ),
    ]


def _smoke_trace(
    *,
    session_id: str,
    source: str,
    model: str,
    system_prompt: str,
    user_id: str,
    end_reason: str,
    turns: list[tuple[str, str, str | None, str | None]],
) -> HermesTrace:
    built: list[HermesTurn] = []
    for index, (role, content, reasoning, tool_name) in enumerate(turns):
        built.append(
            HermesTurn(
                turn_id=f"turn_{index:04d}",
                role=role,
                content=content,
                index=index,
                tool_name=tool_name,
                reasoning=reasoning,
            )
        )
    return HermesTrace(
        trace_id=session_id,
        session_id=session_id,
        user_id=user_id,
        source=source,
        model=model,
        system_prompt=system_prompt,
        turns=tuple(built),
        end_reason=end_reason,
        labels={"source": source, "model": model, "end_reason": end_reason},
        metadata={"source": "hermes_smoke", "user_id": user_id},
    )
