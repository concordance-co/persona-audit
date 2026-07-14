"""Provider registry invariants: resolution, descriptors, and extension."""

from __future__ import annotations

import pytest

from backend.api.providers import REGISTRY
from backend.api.registry import (
    ProviderSpec,
    ScoreConfig,
    TraceLoadResult,
    get_provider,
    provider_descriptor,
    resolve_provider,
    score_run_id,
    score_table,
)

REQUIRED_DESCRIPTOR_KEYS = {
    "id",
    "label",
    "dataset_label",
    "cohort_label",
    "cohort_plural_label",
    "domain_label",
    "segment_label",
    "action_label",
    "task_label",
    "outcome_label",
    "reward_label",
    "pass_rate_label",
    "copy",
    "features",
}


def test_registry_contains_the_three_shipped_providers() -> None:
    assert set(REGISTRY) == {"tau2", "hermes", "persona_demo"}


@pytest.mark.parametrize("key", ["tau2", "hermes", "persona_demo"])
def test_descriptors_carry_every_key_the_frontend_reads(key: str) -> None:
    descriptor = provider_descriptor(key)
    missing = REQUIRED_DESCRIPTOR_KEYS - set(descriptor)
    assert not missing, f"{key} descriptor missing {sorted(missing)}"
    assert descriptor["id"] == key


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        (None, "tau2"),
        ("tau2", "tau2"),
        ("tau2_public_airline", "tau2"),
        ("tau2_smoke", "tau2"),
        ("hermes", "hermes"),
        ("hermes_local", "hermes"),
        ("hermes_smoke", "hermes"),
        ("Hermes-Agent", "hermes"),
        ("persona_demo", "persona_demo"),
        ("persona_audit_demo", "persona_demo"),
        ("demo", "persona_demo"),
        ("personas", "persona_demo"),
        ("something_unknown", "tau2"),
    ],
)
def test_resolve_provider_normalizes_aliases_and_data_provider_ids(name, expected, monkeypatch) -> None:
    monkeypatch.delenv("PERSONA_AUDIT_PROVIDER", raising=False)
    monkeypatch.delenv("PERSONA_AUDIT_DEFAULT_PROVIDER", raising=False)
    assert resolve_provider(name) == expected


def test_resolve_provider_reads_env_when_unset(monkeypatch) -> None:
    monkeypatch.setenv("PERSONA_AUDIT_PROVIDER", "persona_demo")
    assert resolve_provider(None) == "persona_demo"


def test_score_config_resolution_and_env_overrides(monkeypatch) -> None:
    for spec in REGISTRY.values():
        assert spec.score.run_id_env.startswith("PERSONA_AUDIT_")
        assert spec.score.table_env.startswith("PERSONA_AUDIT_")

    monkeypatch.delenv("PERSONA_AUDIT_SCORE_RUN_ID", raising=False)
    assert score_run_id("tau2") == REGISTRY["tau2"].score.default_run_id
    monkeypatch.setenv("PERSONA_AUDIT_SCORE_RUN_ID", "wr_override")
    assert score_run_id("tau2") == "wr_override"

    monkeypatch.delenv("PERSONA_AUDIT_HERMES_SCORE_TABLE", raising=False)
    assert score_table("hermes") == "persona_audit_hermes_score_rows"
    monkeypatch.setenv("PERSONA_AUDIT_HERMES_SCORE_TABLE", "bad;drop")
    with pytest.raises(ValueError):
        score_table("hermes")


def test_every_loader_returns_a_trace_load_result() -> None:
    for spec in REGISTRY.values():
        result = spec.load_traces()
        assert isinstance(result, TraceLoadResult)
        assert isinstance(result.provider_id, str) and result.provider_id
        assert isinstance(result.source, str) and result.source


def test_a_new_provider_needs_one_module_and_one_registry_entry(monkeypatch) -> None:
    """The extension contract: registering a spec makes it fully resolvable."""

    toy = ProviderSpec(
        key="toy",
        aliases=frozenset({"toy", "toy-demo"}),
        alias_prefixes=("toy",),
        descriptor={"id": "toy", "label": "Toy", "features": {}},
        load_traces=lambda: TraceLoadResult(traces=[], provider_id="toy_local", source="toy fixture"),
        score=ScoreConfig(
            run_id_env="PERSONA_AUDIT_TOY_SCORE_RUN_ID",
            default_run_id="toy_run_1",
            table_env="PERSONA_AUDIT_TOY_SCORE_TABLE",
            default_table="persona_audit_toy_score_rows",
        ),
        local_only=True,
    )
    monkeypatch.setitem(REGISTRY, "toy", toy)

    assert resolve_provider("toy_something") == "toy"
    assert get_provider("toy-demo") is toy
    assert score_run_id("toy") == "toy_run_1"
    assert score_table("toy") == "persona_audit_toy_score_rows"
    traces, provider_id, source = toy.load_traces()
    assert (traces, provider_id, source) == ([], "toy_local", "toy fixture")
