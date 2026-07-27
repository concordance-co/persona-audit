"""Generic scoring workflow for the zero-code normalized local provider."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pipelines_v2.api import (
    CaptureSpec,
    Dataset,
    Example,
    ResidualSite,
    TensorStorage,
    TokenPooling,
    TokenSelector,
    WorkflowSpec,
    WorkflowStep,
)

from backend.api.scoring_spaces import trace_scoring_records
from backend.api.trace_source import load_product_traces
from backend.paths import env_value
from backend.workflows.common import (
    ASSISTANT_LAYER,
    EMOTION_LAYER,
    HIGH_STAKES_LAYER,
    assistant_axis_steps,
    assistant_projection_step,
    emotion_score_step,
    emotion_space_step,
    high_stakes_probe_steps,
    modal_artifact_root,
    scoring_engine,
    scoring_runner_specs,
)

WORKFLOW_NAME = "persona_audit_local_scoring_v1"
MODAL_ARTIFACT_ROOT = modal_artifact_root(WORKFLOW_NAME)


def build_dataset() -> Dataset:
    traces, provider_id, source = load_product_traces("local")
    records = trace_scoring_records(traces)
    limit = int(env_value("PERSONA_AUDIT_LOCAL_SCORE_LIMIT", "0") or "0")
    if limit > 0:
        records = records[:limit]
    examples = [_example_from_record(record, provider_id=provider_id, source=source) for record in records]
    return Dataset.from_examples(examples, name=f"{WORKFLOW_NAME}_{provider_id}")


def build_workflow(dataset: Dataset | None = None) -> WorkflowSpec:
    dataset = dataset or build_dataset()
    coordinate_steps, coordinate_refs = assistant_axis_steps()
    probe_import_steps, probe_inference_steps = high_stakes_probe_steps("capture_local", "trace_mean_residual")
    return WorkflowSpec(
        name=WORKFLOW_NAME,
        steps=(
            WorkflowStep(
                name="capture_local",
                runner="capture_gpu",
                spec=CaptureSpec(
                    engine=scoring_engine("LOCAL", default_max_model_len=16384),
                    dataset=dataset,
                    sites=(
                        ResidualSite(
                            name="trace_mean_residual",
                            site="resid_post",
                            layers=(HIGH_STAKES_LAYER,),
                            tokens=TokenSelector.full_sequence(),
                            pooling=TokenPooling.mean(),
                            storage=TensorStorage(dtype="float16", format="safetensors"),
                        ),
                        ResidualSite(
                            name="assistant_response_mean_residual",
                            site="resid_post",
                            layers=(ASSISTANT_LAYER, EMOTION_LAYER),
                            tokens=TokenSelector.section("assistant_response"),
                            pooling=TokenPooling.mean(),
                            storage=TensorStorage(dtype="float16", format="safetensors"),
                        ),
                    ),
                ),
            ),
            *coordinate_steps,
            assistant_projection_step(
                "score_assistant_axis",
                "capture_local",
                "assistant_response_mean_residual",
                coordinate_refs,
            ),
            emotion_space_step(),
            emotion_score_step("score_emotions", "capture_local", "assistant_response_mean_residual"),
            *probe_import_steps,
            *probe_inference_steps,
        ),
    )


def build_runner_specs() -> dict[str, object]:
    return scoring_runner_specs("LOCAL", WORKFLOW_NAME)


def _example_from_record(record: Mapping[str, Any], *, provider_id: str, source: str) -> Example:
    labels = {str(key): value for key, value in dict(record.get("labels") or {}).items()}
    labels.setdefault("provider_id", provider_id)
    labels.setdefault("source", source)
    metadata = {str(key): value for key, value in dict(record.get("metadata") or {}).items()}
    span = dict(record["assistant_response"])
    metadata["token_sections"] = {"assistant_response": span}
    metadata["section_records"] = [
        {
            "name": "assistant_response",
            "unit": "turn",
            "role": "assistant",
            "index": int(record.get("turn_index", 0)),
            "char_start": int(span["char_start"]),
            "char_end": int(span["char_end"]),
        }
    ]
    return Example(
        key=str(record["example_id"]),
        prompt=str(record["text"]),
        labels=labels,
        metadata=metadata,
    )
