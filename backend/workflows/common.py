"""Shared Modal configuration for Persona Audit's Xenon workflows.

Every workflow in this package runs the same model from the same persistent
volumes. This module is the single place those facts live; workflow files
compose these helpers instead of repeating runner boilerplate.

Operational invariants (see docs/xenon-modal-runbook.md):

- Model weights load from the ``yora-models`` volume at ``/models`` — never
  from a fresh HuggingFace download.
- HF, vLLM compile, and inductor caches live on the same volume and commit
  only on step success.
- Modal runners keep ``enable_workflow_batching=True`` so compatible steps
  share one container (and, for GPU steps, one loaded vLLM engine).
"""

from __future__ import annotations

import os

from pipelines_v2.api import (
    LocalArtifactStore,
    ModalSecret,
    ModalVolumeMount,
    ModalVolumeStore,
    TransferPolicy,
)

from backend.paths import REPO_ROOT

MODEL_ID = "meta-llama/Llama-3.3-70B-Instruct"
MODEL_VOLUME_NAME = "yora-models"
MODEL_VOLUME_PATH = "/models"
ARTIFACT_VOLUME_NAME = "xenon-data"


def env_int(name: str, default: int) -> int:
    return int(os.getenv(name, str(default)))


def env_float(name: str, default: float) -> float:
    return float(os.getenv(name, str(default)))


def env_flag(name: str, default: bool = False) -> bool:
    return os.getenv(name, "1" if default else "0").lower() not in {"0", "false", "no", ""}


def hf_secret() -> ModalSecret:
    return ModalSecret.from_env_var("HF_TOKEN", secret_name="huggingface")


def model_volume_mount() -> ModalVolumeMount:
    return ModalVolumeMount(
        name=MODEL_VOLUME_NAME,
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
        name=ARTIFACT_VOLUME_NAME,
        root=modal_artifact_root(workflow_name),
        transfer_policy=TransferPolicy(allow_large_transfer=True),
    )


def local_artifact_store(workflow_name: str) -> LocalArtifactStore:
    # Anchored to the repo so report artifacts land here even when the CLI
    # runs with a different cwd (e.g. from the xenon checkout).
    return LocalArtifactStore(REPO_ROOT / "artifacts" / workflow_name)
