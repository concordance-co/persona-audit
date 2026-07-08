"""Workflow builder invariants: efficiency settings and artifact anchoring.

These encode the operating rules from docs/xenon-modal-runbook.md so a
refactor can't silently reintroduce per-step cold starts or cwd-relative
artifact paths.
"""

from __future__ import annotations

import json

import pytest

from backend.paths import REPO_ROOT
from backend.workflows import demo_generation, hermes_scoring, tau2_scoring


@pytest.fixture(autouse=True)
def _no_round_file(monkeypatch):
    monkeypatch.delenv(demo_generation.ROUND_FILE_ENV, raising=False)


def _resources(runner_specs, name):
    return runner_specs[name].resources


def test_demo_generation_smoke_dataset_covers_all_tracks():
    dataset = demo_generation.build_dataset()
    tracks = {example.labels["track"] for example in dataset.examples}
    assert tracks == {"sol", "marrow", "control"}
    for example in dataset.examples:
        assert example.prompt[0]["role"] == "system"
        assert example.prompt[-1]["role"] == "user"
        assert example.labels["paired_group_id"]
        assert example.metadata["generation_params"]["temperature"] == pytest.approx(0.45)


def test_demo_generation_round_file_drives_dataset(monkeypatch, tmp_path):
    round_file = tmp_path / "round.json"
    round_file.write_text(
        json.dumps(
            {
                "examples": [
                    {
                        "key": "demo_x_sol_t01",
                        "prompt": [
                            {"role": "system", "content": "s"},
                            {"role": "user", "content": "u"},
                        ],
                        "labels": {"track": "sol"},
                        "metadata": {},
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv(demo_generation.ROUND_FILE_ENV, str(round_file))
    dataset = demo_generation.build_dataset()
    assert [example.key for example in dataset.examples] == ["demo_x_sol_t01"]


def test_demo_generation_workflow_and_runners():
    workflow = demo_generation.build_workflow()
    assert [step.name for step in workflow.steps] == ["generate_round"]
    runner_specs = demo_generation.build_runner_specs()
    assert workflow.steps[0].runner in runner_specs
    resources = _resources(runner_specs, "generation_gpu")
    assert resources.enable_workflow_batching is True
    engine = workflow.steps[0].spec.engine
    assert engine.max_num_seqs > 1
    assert engine.enforce_eager is False


@pytest.mark.parametrize("module", [tau2_scoring, hermes_scoring])
def test_scoring_runners_keep_batching_on(module):
    runner_specs = module.build_runner_specs()
    assert _resources(runner_specs, "capture_gpu").enable_workflow_batching is True
    assert _resources(runner_specs, "analysis_cpu").enable_workflow_batching is True


@pytest.mark.parametrize("module", [demo_generation, tau2_scoring, hermes_scoring])
def test_local_artifacts_anchored_to_repo(module):
    runner_specs = module.build_runner_specs()
    root = runner_specs["report_local"].artifacts.root
    assert root.is_absolute()
    assert REPO_ROOT in root.parents
