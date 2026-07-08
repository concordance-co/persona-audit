"""Tau2 behavior-audit scoring workflow.

This workflow turns normalized Tau2 assistant-turn records into Xenon scores
across the three precomputed spaces used by the product:

- Assistant Axis and released trait vectors
- full emotion vector space
- persisted high-stakes probes
"""

from __future__ import annotations

import os
from typing import Any, Mapping, Sequence

from pipelines_v2.api import (
    CaptureSpec,
    Dataset,
    EmotionPrecomputedVectorSpaceSpec,
    EmotionScoreSpec,
    Example,
    LocalRunnerSpec,
    ModalResources,
    ModalRunnerSpec,
    PersistedProbeImportSpec,
    PersistedProbeInferenceSpec,
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
from papers.voice.emotions.assets import load_asset_manifest as load_emotion_manifest
from papers.voice.emotions.assets import precomputed_vector_space_spec
from backend.api.assistant_traits import audit_assistant_traits
from backend.api.scoring_spaces import HIGH_STAKES_PERSISTED_PROBES, trace_scoring_records
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


WORKFLOW_NAME = "behavior_audit_tau2_scoring_v1"
MODAL_ARTIFACT_ROOT = modal_artifact_root(WORKFLOW_NAME)
ASSISTANT_LAYER = 40
EMOTION_LAYER = 52
HIGH_STAKES_LAYER = 31


def build_dataset() -> Dataset:
    traces, provider_id, source = load_product_traces()
    records = trace_scoring_records(traces)
    limit = int(os.getenv("BEHAVIOR_AUDIT_TAU2_SCORE_LIMIT", "0") or "0")
    if limit > 0:
        records = records[:limit]
    examples = [_example_from_record(record, provider_id=provider_id, source=source) for record in records]
    return Dataset.from_examples(examples, name=f"{WORKFLOW_NAME}_{provider_id}")


def build_workflow(dataset: Dataset | None = None) -> WorkflowSpec:
    dataset = dataset or build_dataset()
    assistant_coordinate_steps: list[WorkflowStep] = []
    assistant_coordinate_refs: list[StepRef] = []
    for spec in assistant_axis_coordinate_specs(traits=audit_assistant_traits(), token_env_var="HF_TOKEN"):
        step_name = _assistant_coordinate_step_name(spec)
        assistant_coordinate_steps.append(WorkflowStep(name=step_name, runner="analysis_cpu", spec=spec))
        assistant_coordinate_refs.append(StepRef(step_name))

    high_stakes_import_steps: list[WorkflowStep] = []
    high_stakes_inference_steps: list[WorkflowStep] = []
    for artifact in HIGH_STAKES_PERSISTED_PROBES:
        artifact_id = str(artifact["artifact_id"])
        import_step = f"import_high_stakes_{artifact_id}"
        score_step = f"score_high_stakes_{_safe_step_name(str(artifact['domain']))}_{_safe_step_name(str(artifact['probe_family']))}_{artifact_id}"
        high_stakes_import_steps.append(
            WorkflowStep(
                name=import_step,
                runner="analysis_cpu",
                spec=PersistedProbeImportSpec(
                    path=f"{artifact['target_root']}/{artifact_id}/result.json",
                    name=f"high_stakes__{artifact['domain']}__{artifact['probe_family']}",
                    metadata={
                        "domain": artifact["domain"],
                        "probe_family": artifact["probe_family"],
                        "source_artifact_id": artifact.get("source_artifact_id"),
                        "source_run_id": artifact.get("source_run_id"),
                        "capture_artifact_id": artifact.get("capture_artifact_id"),
                        "balanced_accuracy": artifact.get("balanced_accuracy"),
                        "training_mode": artifact.get("training_mode"),
                        "train_stages": artifact.get("train_stages"),
                        "stage_epochs": artifact.get("stage_epochs"),
                    },
                ),
            )
        )
        high_stakes_inference_steps.append(
            WorkflowStep(
                name=score_step,
                runner="analysis_cpu",
                depends_on=("capture_tau2", import_step),
                spec=PersistedProbeInferenceSpec(
                    feature=StepRef("capture_tau2").feature("trace_mean_residual"),
                    probe=StepRef(import_step),
                    tokens=TokenSelector.full_sequence(),
                    pooling=TokenPooling.mean(),
                    layers=(HIGH_STAKES_LAYER,),
                    emit_labels=True,
                    score_name=f"high_stakes__{artifact['domain']}__{artifact['probe_family']}",
                ),
            )
        )

    return WorkflowSpec(
        name=WORKFLOW_NAME,
        steps=(
            WorkflowStep(
                name="capture_tau2",
                runner="capture_gpu",
                spec=CaptureSpec(
                    engine=_engine(),
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
            *assistant_coordinate_steps,
            WorkflowStep(
                name="score_assistant_axis",
                runner="analysis_cpu",
                depends_on=("capture_tau2", *(ref.step for ref in assistant_coordinate_refs)),
                spec=ProjectionSpec(
                    feature=StepRef("capture_tau2").feature("assistant_response_mean_residual"),
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
                depends_on=("capture_tau2", "emotion_vector_space"),
                spec=EmotionScoreSpec(
                    feature=StepRef("capture_tau2").feature("assistant_response_mean_residual"),
                    vector_space=StepRef("emotion_vector_space"),
                    concepts=(),
                    layers=(EMOTION_LAYER,),
                    pooling=TokenPooling.mean(),
                    summaries=("mean", "min", "max"),
                    emit_labels=True,
                ),
            ),
            *high_stakes_import_steps,
            *high_stakes_inference_steps,
        ),
    )


def build_runner_specs() -> dict[str, object]:
    modal_store = modal_artifact_store(WORKFLOW_NAME)
    return {
        "capture_gpu": ModalRunnerSpec(
            resources=ModalResources(
                gpu=os.getenv("BEHAVIOR_AUDIT_TAU2_CAPTURE_GPU", "H200:2"),
                cpu=16,
                memory_mb=128 * 1024,
                timeout_seconds=env_int("BEHAVIOR_AUDIT_TAU2_CAPTURE_TIMEOUT", 60 * 60 * 12),
                max_containers=env_int("BEHAVIOR_AUDIT_TAU2_CAPTURE_MAX_CONTAINERS", 1),
                shard_count=env_int("BEHAVIOR_AUDIT_TAU2_CAPTURE_SHARDS", 1),
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
                timeout_seconds=env_int("BEHAVIOR_AUDIT_TAU2_ANALYSIS_TIMEOUT", 60 * 60),
                enable_workflow_batching=True,
                env=shared_cache_env(),
                secrets=(hf_secret(),),
                volumes=(model_volume_mount(),),
            ),
            artifacts=modal_store,
        ),
        "report_local": LocalRunnerSpec(artifacts=local_artifact_store(WORKFLOW_NAME)),
    }


def _engine() -> VLLMEngine:
    return VLLMEngine(
        model_id=MODEL_ID,
        model_path_root=MODEL_VOLUME_PATH,
        max_model_len=env_int("BEHAVIOR_AUDIT_TAU2_MAX_MODEL_LEN", 16384),
        tensor_parallel_size=env_int("BEHAVIOR_AUDIT_TAU2_TENSOR_PARALLEL_SIZE", 2),
        gpu_memory_utilization=env_float("BEHAVIOR_AUDIT_TAU2_GPU_MEMORY_UTILIZATION", 0.95),
        enforce_eager=env_flag("BEHAVIOR_AUDIT_TAU2_ENFORCE_EAGER"),
        max_num_seqs=env_int("BEHAVIOR_AUDIT_TAU2_MAX_NUM_SEQS", 128),
        max_num_batched_tokens=env_int("BEHAVIOR_AUDIT_TAU2_MAX_NUM_BATCHED_TOKENS", 8192),
        enable_prefix_caching=True,
        enable_chunked_prefill=True,
        add_generation_prompt=False,
        enable_thinking=False,
    )


def _emotion_vector_space_spec() -> EmotionPrecomputedVectorSpaceSpec:
    manifest = load_emotion_manifest()
    spec = precomputed_vector_space_spec(manifest)
    return EmotionPrecomputedVectorSpaceSpec(
        path=spec.path,
        repo_id=spec.repo_id,
        filename=spec.filename,
        revision=spec.revision,
        format=spec.format,
        select_layer=EMOTION_LAYER,
        normalize=spec.normalize,
        vector_space_kind=spec.vector_space_kind,
        token_env_var=spec.token_env_var,
        metadata=spec.metadata,
    )


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


def _assistant_coordinate_step_name(spec: Any) -> str:
    name = getattr(spec, "name", None)
    if name:
        return _safe_step_name(str(name))
    trait = getattr(spec, "trait", None)
    if trait:
        return f"assistant_axis_trait_{_safe_step_name(str(trait))}"
    return "assistant_axis_coordinate"


def _safe_step_name(value: str) -> str:
    return "".join(ch.lower() if ch.isalnum() else "_" for ch in value).strip("_")
