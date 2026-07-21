"""Provider registry: the single place a data source plugs into the product.

A provider bundles everything the API needs to serve one dataset: how to load
its traces (:class:`TraceLoadResult`), how its activation scores are resolved
(:class:`ScoreConfig`), how it appears in the UI (``descriptor``), and how its
rows are recognized in a shared Postgres table (``db_provider_id_prefix``).

To add a provider: write one module under ``backend/api/providers/`` exposing a
``SPEC`` (see ``providers/persona_demo.py`` for the smallest example) and add it
to the registry tuple in ``backend/api/providers/__init__.py``. Nothing else in
the serving layer needs editing. See docs/adapter-contract.md.

This module holds only types and resolution logic; the concrete specs live in
``backend.api.providers`` (imported lazily to avoid import cycles).
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, NamedTuple

from backend.api.models import AuditTrace
from backend.paths import env_value

DEFAULT_PROVIDER_ENV = "PERSONA_AUDIT_DEFAULT_PROVIDER"
PROVIDER_ENV = "PERSONA_AUDIT_PROVIDER"

TAU2_PROVIDER = "tau2"
HERMES_PROVIDER = "hermes"
PERSONA_DEMO_PROVIDER = "persona_demo"

_FALLBACK_PROVIDER = TAU2_PROVIDER


class TraceLoadResult(NamedTuple):
    """What every trace loader returns.

    A named tuple (not a bare 3-tuple) because the field order was a recurring
    footgun: existing ``traces, provider_id, source = ...`` unpacking keeps
    working, but loaders can no longer silently swap ``provider_id``/``source``.
    """

    traces: list[AuditTrace]
    provider_id: str
    source: str


@dataclass(frozen=True)
class ScoreConfig:
    """How activation-score rows are located for a provider.

    ``default_run_id`` values are historical: they name real score runs whose
    outputs ship in ``data/`` or live in the maintainer database. Override per
    deployment with ``run_id_env``. A callable default lets a provider pick
    the run id from its active trace source (e.g. hermes: bundled demo vs a
    real state.db).
    """

    run_id_env: str
    default_run_id: str | Callable[[], str]
    table_env: str
    default_table: str


@dataclass(frozen=True)
class ProviderSpec:
    """One registered data source."""

    key: str
    aliases: frozenset[str]
    """Normalized (lowercase, dash-separated) names that resolve to this provider."""
    alias_prefixes: tuple[str, ...]
    """Normalized name prefixes that also resolve here (e.g. any ``hermes-*``)."""
    descriptor: Mapping[str, Any]
    """UI labels, copy, and feature flags; served verbatim to the frontend."""
    load_traces: Callable[[], TraceLoadResult]
    """Local (non-database) trace loader."""
    score: ScoreConfig
    local_only: bool = False
    """True = never consult the trace database (bundled datasets)."""
    db_provider_id_prefix: str | None = None
    """Prefix claiming provider_id rows in shared trace tables (None = the rest)."""
    preferred_db_provider_id: Callable[[], str] | None = None
    """Which provider_id to prefer when the table has several for this provider."""
    supports_reward_math: bool = True
    """False = reward/pass-rate analytics are not meaningful for this source."""
    workflow_from_task: Callable[[Mapping[str, Any]], str] | None = None
    """Optional dataset-specific task -> workflow-label taxonomy (see providers/tau2.py)."""


def _registry() -> dict[str, ProviderSpec]:
    from backend.api.providers import REGISTRY

    return REGISTRY


def provider_keys() -> tuple[str, ...]:
    return tuple(_registry())


def resolve_provider(provider: str | None = None) -> str:
    """Normalize any provider name/alias/data-provider-id to a registry key."""

    raw = provider or env_value(PROVIDER_ENV) or env_value(DEFAULT_PROVIDER_ENV) or _FALLBACK_PROVIDER
    normalized = str(raw).strip().lower().replace("_", "-")
    registry = _registry()
    if normalized in registry:
        return normalized
    for spec in registry.values():
        if normalized in spec.aliases:
            return spec.key
    for spec in registry.values():
        if any(normalized.startswith(prefix) for prefix in spec.alias_prefixes):
            return spec.key
    return _FALLBACK_PROVIDER


def get_provider(provider: str | None = None) -> ProviderSpec:
    return _registry()[resolve_provider(provider)]


def provider_descriptor(provider: str | None = None) -> dict[str, Any]:
    return dict(get_provider(provider).descriptor)


def score_run_id(provider: str | None = None) -> str:
    config = get_provider(provider).score
    override = env_value(config.run_id_env)
    if override:
        return override
    default = config.default_run_id
    return default() if callable(default) else default


def score_table(provider: str | None = None) -> str:
    from backend.api.db import safe_identifier

    config = get_provider(provider).score
    return safe_identifier(env_value(config.table_env) or config.default_table)
