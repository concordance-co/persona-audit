"""Score normalized demo traces through the product scoring pipeline.

Reuses the Tau2 scoring workflow's capture/projection/emotion/probe steps —
same model, layers, and surfaces the dashboard shows — over the demo traces
produced by ``factory/scripts/demo_hillclimb.py normalize``. Keeping the
surfaces identical is what makes Stage 2's gate meaningful: the demo passes
when the *product's* scored surfaces separate the tracks.

Scoring examples carry the demo pairing labels (``track``,
``paired_group_id``, ...) so the score artifacts (emitted with labels) can be
fed straight into factory/hillclimb/separation.py.
"""

from __future__ import annotations

from dataclasses import replace

from pipelines_v2.api import Dataset, WorkflowSpec

from backend.api.scoring_spaces import trace_scoring_records
from backend.paths import REPO_ROOT, env_value
from backend.workflows import tau2_scoring
from backend.workflows.common import local_artifact_store, modal_artifact_root, modal_artifact_store
from backend.workflows.tau2_scoring import _example_from_record
from factory.hillclimb.normalize import load_traces
from factory.hillclimb.rounds import PROVIDER_ID

WORKFLOW_NAME = "persona_audit_demo_scoring_v1"
MODAL_ARTIFACT_ROOT = modal_artifact_root(WORKFLOW_NAME)
TRACES_FILE_ENV = "PERSONA_AUDIT_DEMO_TRACES_FILE"
# Default to the shipped demo dataset so the workflow (and the live scoring
# test) works on a fresh clone; the hill-climb driver overrides this env var
# to point at its per-iteration normalized traces.
DEFAULT_TRACES_FILE = REPO_ROOT / "data" / "demo" / "normalized_traces.json"

_DEMO_LABELS = (
    "track",
    "paired_group_id",
    "seed_id",
    "persona_prompt_id",
    "sensitivity_tier",
    "decision_type",
)


def build_dataset() -> Dataset:
    traces_file = env_value(TRACES_FILE_ENV, str(DEFAULT_TRACES_FILE))
    traces = load_traces(traces_file)
    if not traces:
        raise RuntimeError(f"No demo traces found in {traces_file}; run the driver's normalize step first")
    trace_labels = {trace.trace_id: dict(trace.labels) for trace in traces}
    examples = []
    for record in trace_scoring_records(traces):
        labels = dict(record.get("labels") or {})
        source_labels = trace_labels.get(str(record["trace_id"]), {})
        for label in _DEMO_LABELS:
            if label in source_labels:
                labels[label] = source_labels[label]
        record = {**record, "labels": labels}
        examples.append(_example_from_record(record, provider_id=PROVIDER_ID, source="demo_generation"))
    return Dataset.from_examples(examples, name="persona_audit_demo_scoring")


def build_workflow(dataset: Dataset | None = None) -> WorkflowSpec:
    workflow = tau2_scoring.build_workflow(dataset or build_dataset())
    return replace(workflow, name=WORKFLOW_NAME)


def build_runner_specs() -> dict[str, object]:
    # Same runners as Tau2 scoring (and the same env knobs), but demo score
    # artifacts land under this workflow's own artifact roots.
    specs = tau2_scoring.build_runner_specs()
    modal_store = modal_artifact_store(WORKFLOW_NAME)
    for name, spec in specs.items():
        if hasattr(spec, "artifacts") and name != "report_local":
            specs[name] = replace(spec, artifacts=modal_store)
    specs["report_local"] = replace(specs["report_local"], artifacts=local_artifact_store(WORKFLOW_NAME))
    return specs
