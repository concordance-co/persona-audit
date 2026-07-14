"""Shared Modal configuration and step builders for Persona Audit's Xenon workflows.

Every workflow in this package runs the same model from the same persistent
volumes. This module is the single place those facts live; workflow files
compose these helpers instead of repeating runner/engine/step boilerplate.

Bring-your-own-Modal: all infra names are env knobs so the workflows run on any
Modal account (see ``backend/scripts/bootstrap_modal.py`` to initialize one):

- ``PERSONA_AUDIT_MODEL_VOLUME``  volume holding model weights (default
  ``persona-audit-models``), mounted at ``/models``.
- ``PERSONA_AUDIT_DATA_VOLUME``   volume holding workflow artifacts (default
  ``persona-audit-data``).
- ``PERSONA_AUDIT_HF_SECRET``     Modal secret name wrapping ``HF_TOKEN``
  (default ``huggingface``).
- ``PERSONA_AUDIT_MODEL_ID``      model to capture with. Default
  ``meta-llama/Llama-3.3-70B-Instruct`` — note the assistant-axis and emotion
  vector spaces are precomputed against this model at the layers below, so
  changing it changes the science, not just the cost.

Operational invariants (see docs/xenon-modal-runbook.md):

- Model weights load from the model volume at ``/models`` — never from a
  fresh HuggingFace download inside a capture step.
- HF, vLLM compile, and inductor caches live on the same volume and commit
  only on step success.
- Modal runners keep ``enable_workflow_batching=True`` so compatible steps
  share one container (and, for GPU steps, one loaded vLLM engine).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pipelines_v2.api import (
    EmotionPrecomputedVectorSpaceSpec,
    EmotionScoreSpec,
    LocalArtifactStore,
    LocalRunnerSpec,
    ModalResources,
    ModalRunnerSpec,
    ModalSecret,
    ModalVolumeMount,
    ModalVolumeStore,
    PersistedProbeImportSpec,
    PersistedProbeInferenceSpec,
    ProjectionSpec,
    StepRef,
    TokenPooling,
    TokenSelector,
    TransferPolicy,
    VLLMEngine,
    WorkflowStep,
)

from backend.paths import REPO_ROOT, env_value


def model_id() -> str:
    return env_value("PERSONA_AUDIT_MODEL_ID", "meta-llama/Llama-3.3-70B-Instruct")


def model_volume_name() -> str:
    return env_value("PERSONA_AUDIT_MODEL_VOLUME", "persona-audit-models")


def artifact_volume_name() -> str:
    return env_value("PERSONA_AUDIT_DATA_VOLUME", "persona-audit-data")


def hf_secret_name() -> str:
    return env_value("PERSONA_AUDIT_HF_SECRET", "huggingface")


# Backwards-compatible constant-style access (resolved at import time for
# dataset naming; runner/engine builders below resolve lazily instead).
MODEL_ID = model_id()
MODEL_VOLUME_PATH = "/models"

# Capture layers. These are Llama-3.3-70B-specific: the released assistant-axis
# and emotion vector spaces were computed at these layers, and the persisted
# high-stakes probes at layer 31. Changing PERSONA_AUDIT_MODEL_ID requires
# recomputing the vector spaces and choosing new layers.
ASSISTANT_LAYER = 40
EMOTION_LAYER = 52
HIGH_STAKES_LAYER = 31


def env_int(name: str, default: int) -> int:
    return int(env_value(name, str(default)))


def env_float(name: str, default: float) -> float:
    return float(env_value(name, str(default)))


def env_flag(name: str, default: bool = False) -> bool:
    return env_value(name, "1" if default else "0").lower() not in {"0", "false", "no"}


def high_stakes_probes_enabled() -> bool:
    """Persisted-probe steps need probe artifacts on YOUR data volume.

    The shipped probe artifacts live on the maintainer's volume, so this
    defaults off for outside clones; the dashboard's bundled high-stakes
    surfaces are unaffected (they read the shipped caches).
    """

    return env_flag("PERSONA_AUDIT_ENABLE_HIGH_STAKES_PROBES", default=False)


def hf_secret() -> ModalSecret:
    return ModalSecret.from_env_var("HF_TOKEN", secret_name=hf_secret_name())


def model_volume_mount() -> ModalVolumeMount:
    return ModalVolumeMount(
        name=model_volume_name(),
        mount_path=MODEL_VOLUME_PATH,
        create_if_missing=True,
        commit_on_success=True,
    )


def shared_cache_env() -> dict[str, str]:
    return {
        "VLLM_CACHE_ROOT": MODEL_VOLUME_PATH,
        "HF_HOME": f"{MODEL_VOLUME_PATH}/hf_home",
        "TRANSFORMERS_CACHE": f"{MODEL_VOLUME_PATH}/hf_home/transformers",
        "TORCHINDUCTOR_CACHE_DIR": f"{MODEL_VOLUME_PATH}/torch_compile_cache",
    }


def modal_artifact_root(workflow_name: str) -> str:
    return f"/data/artifacts/{workflow_name}"


def modal_artifact_store(workflow_name: str) -> ModalVolumeStore:
    return ModalVolumeStore(
        name=artifact_volume_name(),
        root=modal_artifact_root(workflow_name),
        transfer_policy=TransferPolicy(allow_large_transfer=True),
    )


def local_artifact_store(workflow_name: str) -> LocalArtifactStore:
    # Anchored to the repo so report artifacts land here even when the CLI
    # runs with a different cwd (e.g. from the xenon checkout).
    return LocalArtifactStore(REPO_ROOT / "artifacts" / workflow_name)


def localize_artifact(artifact_root: str, artifact_id: str, cache_root: Path) -> Path:
    """Pull one Modal artifact directory into a local cache and return its path."""

    store = ModalVolumeStore(
        name=artifact_volume_name(),
        root=artifact_root,
        local_cache_root=Path(cache_root) / Path(artifact_root).name,
        transfer_policy=TransferPolicy(allow_large_transfer=True),
    )
    return store.localize(artifact_id)


def scoring_runner_specs(env_prefix: str, workflow_name: str, *, default_gpu: str = "H200:2") -> dict[str, object]:
    """The shared capture-GPU / analysis-CPU / report-local runner catalog.

    ``env_prefix`` selects the per-workflow knob family, e.g. ``TAU2`` reads
    ``PERSONA_AUDIT_TAU2_CAPTURE_GPU`` and friends.
    """

    modal_store = modal_artifact_store(workflow_name)
    return {
        "capture_gpu": ModalRunnerSpec(
            resources=ModalResources(
                gpu=env_value(f"PERSONA_AUDIT_{env_prefix}_CAPTURE_GPU", default_gpu),
                cpu=16,
                memory_mb=128 * 1024,
                timeout_seconds=env_int(f"PERSONA_AUDIT_{env_prefix}_CAPTURE_TIMEOUT", 60 * 60 * 12),
                max_containers=env_int(f"PERSONA_AUDIT_{env_prefix}_CAPTURE_MAX_CONTAINERS", 1),
                shard_count=env_int(f"PERSONA_AUDIT_{env_prefix}_CAPTURE_SHARDS", 1),
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
                timeout_seconds=env_int(f"PERSONA_AUDIT_{env_prefix}_ANALYSIS_TIMEOUT", 60 * 60),
                enable_workflow_batching=True,
                env=shared_cache_env(),
                secrets=(hf_secret(),),
                volumes=(model_volume_mount(),),
            ),
            artifacts=modal_store,
        ),
        "report_local": LocalRunnerSpec(artifacts=local_artifact_store(workflow_name)),
    }


def scoring_engine(env_prefix: str, *, default_max_model_len: int) -> VLLMEngine:
    """The shared capture engine; per-workflow knobs via ``env_prefix``."""

    return VLLMEngine(
        model_id=model_id(),
        model_path_root=MODEL_VOLUME_PATH,
        max_model_len=env_int(f"PERSONA_AUDIT_{env_prefix}_MAX_MODEL_LEN", default_max_model_len),
        tensor_parallel_size=env_int(f"PERSONA_AUDIT_{env_prefix}_TENSOR_PARALLEL_SIZE", 2),
        gpu_memory_utilization=env_float(f"PERSONA_AUDIT_{env_prefix}_GPU_MEMORY_UTILIZATION", 0.95),
        enforce_eager=env_flag(f"PERSONA_AUDIT_{env_prefix}_ENFORCE_EAGER"),
        max_num_seqs=env_int(f"PERSONA_AUDIT_{env_prefix}_MAX_NUM_SEQS", 128),
        max_num_batched_tokens=env_int(f"PERSONA_AUDIT_{env_prefix}_MAX_NUM_BATCHED_TOKENS", 8192),
        enable_prefix_caching=True,
        enable_chunked_prefill=True,
        add_generation_prompt=False,
        enable_thinking=False,
    )


def assistant_axis_steps(runner: str = "analysis_cpu") -> tuple[list[WorkflowStep], list[StepRef]]:
    """Coordinate-vector steps for the assistant axis + audited traits."""

    from papers.voice.assistant_axis.assets import coordinate_specs

    from backend.api.assistant_traits import audit_assistant_traits

    steps: list[WorkflowStep] = []
    refs: list[StepRef] = []
    for spec in coordinate_specs(traits=audit_assistant_traits(), token_env_var="HF_TOKEN"):
        step_name = assistant_coordinate_step_name(spec)
        steps.append(WorkflowStep(name=step_name, runner=runner, spec=spec))
        refs.append(StepRef(step_name))
    return steps, refs


def assistant_projection_step(
    name: str, capture_step: str, feature: str, refs: list[StepRef], runner: str = "analysis_cpu"
) -> WorkflowStep:
    return WorkflowStep(
        name=name,
        runner=runner,
        depends_on=(capture_step, *(ref.step for ref in refs)),
        spec=ProjectionSpec(
            feature=StepRef(capture_step).feature(feature),
            coordinates=tuple(refs),
            layers=(ASSISTANT_LAYER,),
            pooling=TokenPooling.mean(),
            summaries=("mean", "min", "max", "trend"),
            emit_labels=True,
        ),
    )


def emotion_space_step(runner: str = "analysis_cpu") -> WorkflowStep:
    return WorkflowStep(name="emotion_vector_space", runner=runner, spec=emotion_vector_space_spec())


def emotion_score_step(name: str, capture_step: str, feature: str, runner: str = "analysis_cpu") -> WorkflowStep:
    return WorkflowStep(
        name=name,
        runner=runner,
        depends_on=(capture_step, "emotion_vector_space"),
        spec=EmotionScoreSpec(
            feature=StepRef(capture_step).feature(feature),
            vector_space=StepRef("emotion_vector_space"),
            concepts=(),
            layers=(EMOTION_LAYER,),
            pooling=TokenPooling.mean(),
            summaries=("mean", "min", "max"),
            emit_labels=True,
        ),
    )


def high_stakes_probe_steps(
    capture_step: str, feature: str, runner: str = "analysis_cpu"
) -> tuple[list[WorkflowStep], list[WorkflowStep]]:
    """Import + inference steps for the persisted high-stakes probes.

    Returns two empty lists unless :func:`high_stakes_probes_enabled` — the
    probe artifacts referenced here must exist on the configured data volume.
    """

    from backend.api.scoring_spaces import HIGH_STAKES_PERSISTED_PROBES

    if not high_stakes_probes_enabled():
        return [], []
    import_steps: list[WorkflowStep] = []
    inference_steps: list[WorkflowStep] = []
    for artifact in HIGH_STAKES_PERSISTED_PROBES:
        artifact_id = str(artifact["artifact_id"])
        import_step = f"import_high_stakes_{artifact_id}"
        score_step = (
            f"score_high_stakes_{safe_step_name(str(artifact['domain']))}"
            f"_{safe_step_name(str(artifact['probe_family']))}_{artifact_id}"
        )
        import_steps.append(
            WorkflowStep(
                name=import_step,
                runner=runner,
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
        inference_steps.append(
            WorkflowStep(
                name=score_step,
                runner=runner,
                depends_on=(capture_step, import_step),
                spec=PersistedProbeInferenceSpec(
                    feature=StepRef(capture_step).feature(feature),
                    probe=StepRef(import_step),
                    tokens=TokenSelector.full_sequence(),
                    pooling=TokenPooling.mean(),
                    layers=(HIGH_STAKES_LAYER,),
                    emit_labels=True,
                    score_name=f"high_stakes__{artifact['domain']}__{artifact['probe_family']}",
                ),
            )
        )
    return import_steps, inference_steps


def emotion_vector_space_spec() -> EmotionPrecomputedVectorSpaceSpec:
    from papers.voice.emotions.assets import load_asset_manifest, precomputed_vector_space_spec

    manifest = load_asset_manifest()
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


def assistant_coordinate_step_name(spec: Any) -> str:
    name = getattr(spec, "name", None)
    if name:
        return safe_step_name(str(name))
    trait = getattr(spec, "trait", None)
    if trait:
        return f"assistant_axis_trait_{safe_step_name(str(trait))}"
    return "assistant_axis_coordinate"


def safe_step_name(value: str) -> str:
    return "".join(ch.lower() if ch.isalnum() else "_" for ch in value).strip("_")
