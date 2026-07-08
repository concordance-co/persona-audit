"""Hermes behavior-audit scoring workflow.

Scores local Hermes assistant turns across the shared Persona Audit spaces:

- Assistant Axis and released trait vectors
- full emotion vector space
- optional reasoning-section capture for thought-vs-said analysis
"""

from __future__ import annotations

import os
from typing import Any, Mapping

from pipelines_v2.api import (
    CaptureSpec,
    Dataset,
    EmotionScoreSpec,
    Example,
    LocalRunnerSpec,
    ModalResources,
    ModalRunnerSpec,
    ProjectionSpec,
    ResidualSite,
    StepRef,
    TensorStorage,
    TokenPooling,
    TokenSelector,
    VLLMEngine,
    WorkflowSpec,
    WorkflowStep,
)

from papers.voice.assistant_axis.assets import coordinate_specs as assistant_axis_coordinate_specs

from backend.api.assistant_traits import audit_assistant_traits
from backend.api.scoring_spaces import trace_scoring_records
from backend.api.trace_source import load_product_traces
from backend.workflows.common import (
    MODEL_ID,
    MODEL_VOLUME_PATH,
    env_flag,
    env_float,
    env_int,
    hf_secret,
    local_artifact_store,
    modal_artifact_root,
    modal_artifact_store,
    model_volume_mount,
    shared_cache_env,
)
from backend.workflows.tau2_scoring import (
    ASSISTANT_LAYER,
    EMOTION_LAYER,
    _assistant_coordinate_step_name,
    _emotion_vector_space_spec,
)


WORKFLOW_NAME = "behavior_audit_hermes_scoring_v1"
MODAL_ARTIFACT_ROOT = modal_artifact_root(WORKFLOW_NAME)
ASSISTANT_RESIDUAL_FEATURE = "assistant_response_mean_residual"
REASONING_RESIDUAL_FEATURE = "assistant_reasoning_mean_residual"


def build_dataset() -> Dataset:
    traces, provider_id, source = load_product_traces("hermes", prefer_neon=False)
    trace_filter = {
        token.strip()
        for token in os.getenv("BEHAVIOR_AUDIT_HERMES_SCORE_TRACE_IDS", "").split(",")
        if token.strip()
    }
    if trace_filter:
        traces = [trace for trace in traces if trace.trace_id in trace_filter]
        missing = trace_filter - {trace.trace_id for trace in traces}
        if missing:
            raise ValueError(f"BEHAVIOR_AUDIT_HERMES_SCORE_TRACE_IDS not found in Hermes sessions: {sorted(missing)}")
    limit = int(os.getenv("BEHAVIOR_AUDIT_HERMES_SCORE_LIMIT", "0") or "0")
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
    assistant_coordinate_steps: list[WorkflowStep] = []
    assistant_coordinate_refs: list[StepRef] = []
    for spec in assistant_axis_coordinate_specs(traits=audit_assistant_traits(), token_env_var="HF_TOKEN"):
        step_name = _assistant_coordinate_step_name(spec)
        assistant_coordinate_steps.append(WorkflowStep(name=step_name, runner="analysis_cpu", spec=spec))
        assistant_coordinate_refs.append(StepRef(step_name))

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
            WorkflowStep(
                name="score_reasoning_assistant_axis",
                runner="analysis_cpu",
                depends_on=("capture_hermes", *(ref.step for ref in assistant_coordinate_refs)),
                spec=ProjectionSpec(
                    feature=StepRef("capture_hermes").feature(REASONING_RESIDUAL_FEATURE),
                    coordinates=tuple(assistant_coordinate_refs),
                    layers=(ASSISTANT_LAYER,),
                    pooling=TokenPooling.mean(),
                    summaries=("mean", "min", "max", "trend"),
                    emit_labels=True,
                ),
            ),
            WorkflowStep(
                name="score_reasoning_emotions",
                runner="analysis_cpu",
                depends_on=("capture_hermes", "emotion_vector_space"),
                spec=EmotionScoreSpec(
                    feature=StepRef("capture_hermes").feature(REASONING_RESIDUAL_FEATURE),
                    vector_space=StepRef("emotion_vector_space"),
                    concepts=(),
                    layers=(EMOTION_LAYER,),
                    pooling=TokenPooling.mean(),
                    summaries=("mean", "min", "max"),
                    emit_labels=True,
                ),
            ),
        ]

    return WorkflowSpec(
        name=WORKFLOW_NAME,
        steps=(
            WorkflowStep(
                name="capture_hermes",
                runner="capture_gpu",
                spec=CaptureSpec(
                    engine=_hermes_engine(),
                    dataset=dataset,
                    sites=tuple(capture_sites),
                ),
            ),
            *assistant_coordinate_steps,
            WorkflowStep(
                name="score_assistant_axis",
                runner="analysis_cpu",
                depends_on=("capture_hermes", *(ref.step for ref in assistant_coordinate_refs)),
                spec=ProjectionSpec(
                    feature=StepRef("capture_hermes").feature(ASSISTANT_RESIDUAL_FEATURE),
                    coordinates=tuple(assistant_coordinate_refs),
                    layers=(ASSISTANT_LAYER,),
                    pooling=TokenPooling.mean(),
                    summaries=("mean", "min", "max", "trend"),
                    emit_labels=True,
                ),
            ),
            WorkflowStep(
                name="emotion_vector_space",
                runner="analysis_cpu",
                spec=_emotion_vector_space_spec(),
            ),
            WorkflowStep(
                name="score_emotions",
                runner="analysis_cpu",
                depends_on=("capture_hermes", "emotion_vector_space"),
                spec=EmotionScoreSpec(
                    feature=StepRef("capture_hermes").feature(ASSISTANT_RESIDUAL_FEATURE),
                    vector_space=StepRef("emotion_vector_space"),
                    concepts=(),
                    layers=(EMOTION_LAYER,),
                    pooling=TokenPooling.mean(),
                    summaries=("mean", "min", "max"),
                    emit_labels=True,
                ),
            ),
            *reasoning_steps,
        ),
    )


def build_runner_specs() -> dict[str, object]:
    modal_store = modal_artifact_store(WORKFLOW_NAME)
    return {
        "capture_gpu": ModalRunnerSpec(
            resources=ModalResources(
                gpu=os.getenv("BEHAVIOR_AUDIT_HERMES_CAPTURE_GPU", "H200:2"),
                cpu=16,
                memory_mb=128 * 1024,
                timeout_seconds=env_int("BEHAVIOR_AUDIT_HERMES_CAPTURE_TIMEOUT", 60 * 60 * 12),
                max_containers=env_int("BEHAVIOR_AUDIT_HERMES_CAPTURE_MAX_CONTAINERS", 1),
                shard_count=env_int("BEHAVIOR_AUDIT_HERMES_CAPTURE_SHARDS", 1),
                enable_workflow_batching=True,
                env=shared_cache_env(),
                secrets=(hf_secret(),),
                volumes=(model_volume_mount(),),
            ),
            artifacts=modal_store,
        ),
        "analysis_cpu": ModalRunnerSpec(
            resources=ModalResources(
                cpu=4,
                memory_mb=16 * 1024,
                timeout_seconds=env_int("BEHAVIOR_AUDIT_HERMES_ANALYSIS_TIMEOUT", 60 * 60),
                enable_workflow_batching=True,
                env=shared_cache_env(),
                secrets=(hf_secret(),),
                volumes=(model_volume_mount(),),
            ),
            artifacts=modal_store,
        ),
        "report_local": LocalRunnerSpec(artifacts=local_artifact_store(WORKFLOW_NAME)),
    }


def _hermes_engine() -> VLLMEngine:
    return VLLMEngine(
        model_id=MODEL_ID,
        model_path_root=MODEL_VOLUME_PATH,
        max_model_len=env_int("BEHAVIOR_AUDIT_HERMES_MAX_MODEL_LEN", 40960),
        tensor_parallel_size=env_int("BEHAVIOR_AUDIT_HERMES_TENSOR_PARALLEL_SIZE", 2),
        gpu_memory_utilization=env_float("BEHAVIOR_AUDIT_HERMES_GPU_MEMORY_UTILIZATION", 0.95),
        enforce_eager=env_flag("BEHAVIOR_AUDIT_HERMES_ENFORCE_EAGER"),
        max_num_seqs=env_int("BEHAVIOR_AUDIT_HERMES_MAX_NUM_SEQS", 128),
        max_num_batched_tokens=env_int("BEHAVIOR_AUDIT_HERMES_MAX_NUM_BATCHED_TOKENS", 8192),
        enable_prefix_caching=True,
        enable_chunked_prefill=True,
        add_generation_prompt=False,
        enable_thinking=False,
    )


def _include_reasoning(dataset: Dataset) -> bool:
    if os.getenv("BEHAVIOR_AUDIT_HERMES_INCLUDE_REASONING", "1").strip().lower() in {"0", "false", "no"}:
        return False
    examples = getattr(dataset, "examples", ())
    return any(
        isinstance(example.metadata.get("token_sections"), Mapping)
        and "assistant_reasoning" in example.metadata["token_sections"]
        for example in examples
    )


def main() -> None:
    workflow = build_workflow()
    print(workflow)


if __name__ == "__main__":
    main()
