"""Product workflow builder invariants: efficiency settings and artifact anchoring.

These encode the operating rules from docs/xenon-modal-runbook.md so a
refactor can't silently reintroduce per-step cold starts or cwd-relative
artifact paths. Factory (demo) workflow invariants live in
tests/factory/test_factory_workflows.py.
"""

from __future__ import annotations

import pytest

from backend.paths import REPO_ROOT
from backend.workflows import hermes_scoring, tau2_scoring


def _resources(runner_specs, name):
    return runner_specs[name].resources


@pytest.mark.parametrize("module", [tau2_scoring, hermes_scoring])
def test_scoring_runners_keep_batching_on(module):
    runner_specs = module.build_runner_specs()
    assert _resources(runner_specs, "capture_gpu").enable_workflow_batching is True
    assert _resources(runner_specs, "analysis_cpu").enable_workflow_batching is True


@pytest.mark.parametrize("module", [tau2_scoring, hermes_scoring])
def test_local_artifacts_anchored_to_repo(module):
    runner_specs = module.build_runner_specs()
    root = runner_specs["report_local"].artifacts.root
    assert root.is_absolute()
    assert REPO_ROOT in root.parents


def test_high_stakes_probe_steps_are_gated_off_by_default(monkeypatch):
    monkeypatch.delenv("PERSONA_AUDIT_ENABLE_HIGH_STAKES_PROBES", raising=False)
    monkeypatch.setenv("PERSONA_AUDIT_TAU2_SCORE_LIMIT", "2")
    workflow = tau2_scoring.build_workflow()
    step_names = [step.name for step in workflow.steps]
    assert not any(name.startswith("import_high_stakes_") for name in step_names)

    monkeypatch.setenv("PERSONA_AUDIT_ENABLE_HIGH_STAKES_PROBES", "1")
    workflow = tau2_scoring.build_workflow()
    step_names = [step.name for step in workflow.steps]
    assert any(name.startswith("import_high_stakes_") for name in step_names)
    assert any(name.startswith("score_high_stakes_") for name in step_names)


def test_backend_never_imports_the_factory():
    """The product runtime must not depend on the demo factory."""

    offenders = [
        path
        for path in (REPO_ROOT / "backend").rglob("*.py")
        if "import factory" in path.read_text(encoding="utf-8") or "from factory" in path.read_text(encoding="utf-8")
    ]
    assert not offenders, [str(path) for path in offenders]
