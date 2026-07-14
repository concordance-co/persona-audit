"""Hermes behavior-audit scoring workflow.

Scores local Hermes assistant turns across the shared Persona Audit spaces:

- Assistant Axis and released trait vectors
- full emotion vector space
- optional reasoning-section capture for thought-vs-said analysis

Step construction is shared with the Tau2 workflow via backend.workflows.common.
"""

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
    assistant_axis_steps,
    assistant_projection_step,
    emotion_score_step,
    emotion_space_step,
    modal_artifact_root,
    scoring_engine,
    scoring_runner_specs,
)

WORKFLOW_NAME = "persona_audit_hermes_scoring_v1"
MODAL_ARTIFACT_ROOT = modal_artifact_root(WORKFLOW_NAME)
ASSISTANT_RESIDUAL_FEATURE = "assistant_response_mean_residual"
REASONING_RESIDUAL_FEATURE = "assistant_reasoning_mean_residual"


def build_dataset() -> Dataset:
    traces, provider_id, source = load_product_traces("hermes", prefer_neon=False)
    trace_filter = {
        token.strip() for token in env_value("PERSONA_AUDIT_HERMES_SCORE_TRACE_IDS", "").split(",") if token.strip()
    }
    if trace_filter:
        traces = [trace for trace in traces if trace.trace_id in trace_filter]
        missing = trace_filter - {trace.trace_id for trace in traces}
        if missing:
            raise ValueError(f"PERSONA_AUDIT_HERMES_SCORE_TRACE_IDS not found in Hermes sessions: {sorted(missing)}")
    limit = int(env_value("PERSONA_AUDIT_HERMES_SCORE_LIMIT", "0") or "0")
    if limit > 0:
        traces = traces[:limit]
    trace_context = {
        trace.trace_id: {
            "trace_id": trace.trace_id,
            "session_id": trace.session_id,
            "user_id": trace.user_id,
        }
        for trace in traces
    }
    records = trace_scoring_records(traces)
    examples = [
        _example_from_record(
            record,
            provider_id=provider_id,
            source=source,
            trace_context=trace_context[str(record["trace_id"])],
        )
        for record in records
    ]
    return Dataset.from_examples(examples, name=f"{WORKFLOW_NAME}_{provider_id}")


def _example_from_record(
    record: Mapping[str, Any],
    *,
    provider_id: str,
    source: str,
    trace_context: Mapping[str, Any],
) -> Example:
    labels = {str(key): value for key, value in dict(record.get("labels") or {}).items()}
    labels.setdefault("provider_id", provider_id)
    labels.setdefault("source", source)
    metadata = {str(key): value for key, value in dict(record.get("metadata") or {}).items()}
    metadata.update(trace_context)
    metadata["provider_id"] = provider_id
    response_span = dict(record["assistant_response"])
    token_sections = {"assistant_response": response_span}
    section_records = [
        {
            "name": "assistant_response",
            "unit": "turn",
            "role": "assistant",
            "index": int(record.get("turn_index", 0)),
            "char_start": int(response_span["char_start"]),
            "char_end": int(response_span["char_end"]),
        }
    ]
    reasoning_span = metadata.get("assistant_reasoning")
    if isinstance(reasoning_span, Mapping):
        token_sections["assistant_reasoning"] = dict(reasoning_span)
        section_records.append(
            {
                "name": "assistant_reasoning",
                "unit": "turn",
                "role": "assistant",
                "index": int(record.get("turn_index", 0)),
                "char_start": int(reasoning_span["char_start"]),
                "char_end": int(reasoning_span["char_end"]),
            }
        )
    metadata["token_sections"] = token_sections
    metadata["section_records"] = section_records
    return Example(
        key=str(record["example_id"]),
        prompt=str(record["text"]),
        labels=labels,
        metadata=metadata,
    )


def build_workflow(dataset: Dataset | None = None) -> WorkflowSpec:
    dataset = dataset or build_dataset()
    include_reasoning = _include_reasoning(dataset)
    coordinate_steps, coordinate_refs = assistant_axis_steps()

    capture_sites = [
        ResidualSite(
            name=ASSISTANT_RESIDUAL_FEATURE,
            site="resid_post",
            layers=(ASSISTANT_LAYER, EMOTION_LAYER),
            tokens=TokenSelector.section("assistant_response"),
            pooling=TokenPooling.mean(),
            storage=TensorStorage(dtype="float16", format="safetensors"),
        )
    ]
    if include_reasoning:
        capture_sites.append(
            ResidualSite(
                name=REASONING_RESIDUAL_FEATURE,
                site="resid_post",
                layers=(ASSISTANT_LAYER, EMOTION_LAYER),
                tokens=TokenSelector.section("assistant_reasoning"),
                pooling=TokenPooling.mean(),
                storage=TensorStorage(dtype="float16", format="safetensors"),
            )
        )

    reasoning_steps: list[WorkflowStep] = []
    if include_reasoning:
        reasoning_steps = [
            assistant_projection_step(
                "score_reasoning_assistant_axis", "capture_hermes", REASONING_RESIDUAL_FEATURE, coordinate_refs
            ),
            emotion_score_step("score_reasoning_emotions", "capture_hermes", REASONING_RESIDUAL_FEATURE),
        ]

    return WorkflowSpec(
        name=WORKFLOW_NAME,
        steps=(
            WorkflowStep(
                name="capture_hermes",
                runner="capture_gpu",
                spec=CaptureSpec(
                    engine=scoring_engine("HERMES", default_max_model_len=40960),
                    dataset=dataset,
                    sites=tuple(capture_sites),
                ),
            ),
            *coordinate_steps,
            assistant_projection_step(
                "score_assistant_axis", "capture_hermes", ASSISTANT_RESIDUAL_FEATURE, coordinate_refs
            ),
            emotion_space_step(),
            emotion_score_step("score_emotions", "capture_hermes", ASSISTANT_RESIDUAL_FEATURE),
            *reasoning_steps,
        ),
    )


def build_runner_specs() -> dict[str, object]:
    return scoring_runner_specs("HERMES", WORKFLOW_NAME)


def _include_reasoning(dataset: Dataset) -> bool:
    if env_value("PERSONA_AUDIT_HERMES_INCLUDE_REASONING", "1").strip().lower() in {"0", "false", "no"}:
        return False
    examples = getattr(dataset, "examples", ())
    return any(
        isinstance(example.metadata.get("token_sections"), Mapping)
        and "assistant_reasoning" in example.metadata["token_sections"]
        for example in examples
    )
