"""Score-access provider context and table/run-id resolution.

The ContextVar carries the active provider through nested summary-building
calls (the SQL builders resolve the score table without a provider argument).
Run ids and score tables come from each provider's ScoreConfig (see
backend.api.registry); the summary table is provider-independent.
"""

from __future__ import annotations

from contextvars import ContextVar

from backend.api.db import configured_database_url, safe_identifier
from backend.api.registry import resolve_provider, score_run_id, score_table
from backend.paths import env_value

SCORE_SUMMARY_TABLE = "persona_audit_score_summaries"
SCORE_SUMMARY_TABLE_ENV = "PERSONA_AUDIT_SCORE_SUMMARY_TABLE"

_CURRENT_PROVIDER: ContextVar[str] = ContextVar("persona_audit_score_provider", default="tau2")


def normalized_score_provider(provider: str | None = None) -> str:
    """Registry key for score access; ``None`` keeps the ContextVar's provider."""

    if provider is None:
        return _CURRENT_PROVIDER.get()
    return resolve_provider(provider)


def current_score_run_id(provider: str | None = None) -> str:
    return score_run_id(normalized_score_provider(provider))


def current_score_table() -> str:
    return score_table(_CURRENT_PROVIDER.get())


def score_summary_table() -> str:
    return safe_identifier(env_value(SCORE_SUMMARY_TABLE_ENV) or SCORE_SUMMARY_TABLE)


def database_url() -> str | None:
    return configured_database_url()
