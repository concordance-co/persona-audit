"""Free workflow-plan contract tests: every workflow file plans cleanly.

``WorkflowOrchestrator.plan`` is a static preflight (spec validation +
runner-capability checks) — no Modal auth, no network, no GPU — so this tier
runs in CI and catches contract breaks (bad specs, unknown runners, missing
capabilities) that the builder-shape tests cannot. Actually executing on
Modal is the opt-in ``-m modal_live`` tier under tests/live/.
"""

from __future__ import annotations

import importlib

import pytest
from pipelines_v2.api import WorkflowOrchestrator

WORKFLOW_MODULES = (
    "backend.workflows.tau2_scoring",
    "backend.workflows.hermes_scoring",
    "factory.workflows.demo_generation",
    "factory.workflows.demo_scoring",
)


@pytest.fixture(autouse=True)
def _hermetic_env(monkeypatch):
    monkeypatch.setenv("HF_TOKEN", "dummy-token-for-spec-preflight")
    monkeypatch.setenv("PERSONA_AUDIT_TAU2_SCORE_LIMIT", "3")
    monkeypatch.setenv("PERSONA_AUDIT_HERMES_SCORE_LIMIT", "1")
    monkeypatch.delenv("PERSONA_AUDIT_DEMO_ROUND_FILE", raising=False)
    monkeypatch.delenv("PERSONA_AUDIT_DEMO_TRACES_FILE", raising=False)
    monkeypatch.delenv("PERSONA_AUDIT_ENABLE_HIGH_STAKES_PROBES", raising=False)


def _plan(module_path: str):
    module = importlib.import_module(module_path)
    dataset = module.build_dataset()
    workflow = module.build_workflow(dataset)
    runners = {name: spec.to_runner() for name, spec in module.build_runner_specs().items()}
    return WorkflowOrchestrator(runners=runners).plan(workflow)


@pytest.mark.parametrize("module_path", WORKFLOW_MODULES)
def test_workflow_plans_without_errors(module_path):
    plan = _plan(module_path)
    assert plan.steps
    for step in plan.steps:
        assert not list(step.execution.errors), f"{module_path}:{step.name} -> {list(step.execution.errors)}"
        assert not set(step.execution.missing_capabilities), (
            f"{module_path}:{step.name} missing {sorted(cap.value for cap in step.execution.missing_capabilities)}"
        )


def test_tau2_plan_includes_probe_steps_when_enabled(monkeypatch):
    monkeypatch.setenv("PERSONA_AUDIT_ENABLE_HIGH_STAKES_PROBES", "1")
    plan = _plan("backend.workflows.tau2_scoring")
    step_names = [step.name for step in plan.steps]
    assert any(name.startswith("score_high_stakes_") for name in step_names)
    for step in plan.steps:
        assert not list(step.execution.errors), f"{step.name} -> {list(step.execution.errors)}"
