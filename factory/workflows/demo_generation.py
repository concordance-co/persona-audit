"""Persona Audit demo-data generation workflow.

Generates one round of assistant turns (all seeds x all tracks, batched into a
single vLLM session) through the Xenon/Modal stack. Rounds are produced by the
driver in factory/scripts/demo_hillclimb.py: it writes a round file, points
``PERSONA_AUDIT_DEMO_ROUND_FILE`` at it, and runs this workflow once per
conversation turn. Without a round file, builds the Stage 0 turn-0 examples
for all three tracks as a smoke test.

Run via ``backend/scripts/run_xenon_workflow.sh`` (see docs/xenon-modal-runbook.md).
"""

from __future__ import annotations

import json
from pathlib import Path

from pipelines_v2.api import (
    Dataset,
    Example,
    GenerationRunSpec,
    GenerationSpec,
    LocalRunnerSpec,
    ModalResources,
    ModalRunnerSpec,
    VLLMEngine,
    WorkflowSpec,
    WorkflowStep,
)

from backend.paths import env_value
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
from factory.hillclimb.personas import latest_prompts
from factory.hillclimb.rounds import build_round_examples
from factory.hillclimb.seeds import STAGE0_SEEDS

WORKFLOW_NAME = "persona_audit_demo_generation_v1"
MODAL_ARTIFACT_ROOT = modal_artifact_root(WORKFLOW_NAME)
ROUND_FILE_ENV = "PERSONA_AUDIT_DEMO_ROUND_FILE"

GENERATION_PARAMS = {
    "max_tokens": env_int("PERSONA_AUDIT_DEMO_GENERATION_MAX_TOKENS", 256),
    "temperature": env_float("PERSONA_AUDIT_DEMO_GENERATION_TEMPERATURE", 0.45),
    "top_p": env_float("PERSONA_AUDIT_DEMO_GENERATION_TOP_P", 0.9),
}


def _round_examples() -> list[dict[str, object]]:
    round_file = env_value(ROUND_FILE_ENV)
    if round_file:
        payload = json.loads(Path(round_file).read_text(encoding="utf-8"))
        return list(payload["examples"])
    # Smoke default: Stage 0 seed, turn 0, all three tracks.
    return build_round_examples(STAGE0_SEEDS, latest_prompts(), {}, 0, stage=0)


def build_dataset() -> Dataset:
    examples = [
        Example(
            key=str(example["key"]),
            prompt=example["prompt"],
            labels=dict(example.get("labels") or {}),
            metadata={
                **dict(example.get("metadata") or {}),
                "generation_model": MODEL_ID,
                "generation_params": GENERATION_PARAMS,
            },
        )
        for example in _round_examples()
    ]
    return Dataset.from_examples(examples, name="persona_audit_demo_generation_round")


def build_workflow(dataset: Dataset | None = None) -> WorkflowSpec:
    return WorkflowSpec(
        name=WORKFLOW_NAME,
        steps=(
            WorkflowStep(
                name="generate_round",
                runner="generation_gpu",
                spec=GenerationRunSpec(
                    engine=_engine(),
                    dataset=dataset or build_dataset(),
                    generation=GenerationSpec(
                        enabled=True,
                        max_tokens=int(GENERATION_PARAMS["max_tokens"]),
                        temperature=float(GENERATION_PARAMS["temperature"]),
                        top_p=float(GENERATION_PARAMS["top_p"]),
                    ),
                ),
            ),
        ),
    )


def build_runner_specs() -> dict[str, object]:
    return {
        "generation_gpu": ModalRunnerSpec(
            resources=ModalResources(
                gpu=env_value("PERSONA_AUDIT_DEMO_GENERATION_GPU", "H100:2"),
                cpu=8,
                memory_mb=96 * 1024,
                timeout_seconds=env_int("PERSONA_AUDIT_DEMO_GENERATION_TIMEOUT", 60 * 60 * 2),
                max_containers=1,
                # Coalesce ready generation steps into one Modal call so the
                # vLLM engine loads once per run instead of once per step.
                enable_workflow_batching=True,
                env=shared_cache_env(),
                secrets=(hf_secret(),),
                volumes=(model_volume_mount(),),
            ),
            artifacts=modal_artifact_store(WORKFLOW_NAME),
        ),
        "report_local": LocalRunnerSpec(artifacts=local_artifact_store(WORKFLOW_NAME)),
    }


def _engine() -> VLLMEngine:
    return VLLMEngine(
        model_id=MODEL_ID,
        model_path_root=MODEL_VOLUME_PATH,
        max_model_len=env_int("PERSONA_AUDIT_DEMO_GENERATION_MAX_MODEL_LEN", 4096),
        tensor_parallel_size=env_int("PERSONA_AUDIT_DEMO_GENERATION_TENSOR_PARALLEL_SIZE", 2),
        gpu_memory_utilization=env_float("PERSONA_AUDIT_DEMO_GENERATION_GPU_MEMORY_UTILIZATION", 0.9),
        enforce_eager=env_flag("PERSONA_AUDIT_DEMO_GENERATION_ENFORCE_EAGER"),
        max_num_seqs=env_int("PERSONA_AUDIT_DEMO_GENERATION_MAX_NUM_SEQS", 16),
        max_num_batched_tokens=env_int("PERSONA_AUDIT_DEMO_GENERATION_MAX_NUM_BATCHED_TOKENS", 4096),
        enable_prefix_caching=True,
        enable_chunked_prefill=True,
        add_generation_prompt=True,
        enable_thinking=False,
    )
