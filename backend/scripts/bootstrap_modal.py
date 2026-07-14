"""Initialize (or verify) the Modal resources the scoring workflows need.

Persona Audit's GPU workflows expect three things on YOUR Modal account:

1. a model volume (``PERSONA_AUDIT_MODEL_VOLUME``, default ``persona-audit-models``)
   holding the capture model's weights under ``/models/<model-id>``,
2. a data volume (``PERSONA_AUDIT_DATA_VOLUME``, default ``persona-audit-data``)
   where workflow artifacts land,
3. a Modal secret (``PERSONA_AUDIT_HF_SECRET``, default ``huggingface``)
   wrapping an ``HF_TOKEN`` that can download the model.

Usage (idempotent):

    uv run python -m backend.scripts.bootstrap_modal            # create + download
    uv run python -m backend.scripts.bootstrap_modal --check    # read-only verify

``--check`` exits non-zero with an actionable message per missing piece; the
live Modal tests use it as their preflight. The model download runs as a CPU
Modal function writing straight to the volume (Llama models require an
accepted license on the HF account behind HF_TOKEN; the 70B is ~140 GB).
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys

from backend.paths import env_value, load_dotenv
from backend.workflows.common import (
    MODEL_VOLUME_PATH,
    artifact_volume_name,
    hf_secret_name,
    model_id,
    model_volume_name,
)

DOWNLOAD_TIMEOUT_SECONDS = 60 * 60 * 4


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--check", action="store_true", help="verify only; never create or download")
    args = parser.parse_args()

    load_dotenv()
    problems: list[str] = []

    if not _modal_authenticated():
        _report(
            problems,
            "Modal auth",
            False,
            "run `modal setup` (or set MODAL_TOKEN_ID/MODAL_TOKEN_SECRET)",
        )
        _summarize(problems)
        return 1
    _report(problems, "Modal auth", True, "")

    for volume in (model_volume_name(), artifact_volume_name()):
        exists = _volume_exists(volume)
        if not exists and not args.check:
            subprocess.run(["modal", "volume", "create", volume], check=True)
            exists = True
        _report(problems, f"volume {volume}", exists, f"run `modal volume create {volume}`")

    secret = hf_secret_name()
    secret_ok = _secret_exists(secret)
    _report(
        problems,
        f"secret {secret} (HF_TOKEN)",
        secret_ok,
        f"run `modal secret create {secret} HF_TOKEN=<your huggingface token>`",
    )

    model = model_id()
    model_ok = _model_on_volume(model_volume_name(), model)
    if not model_ok and not args.check and secret_ok:
        print(f"downloading {model} onto volume {model_volume_name()} (this can take a while)...")
        _download_model(model)
        model_ok = _model_on_volume(model_volume_name(), model)
    _report(
        problems,
        f"model {model} on {model_volume_name()}",
        model_ok,
        "re-run without --check (needs the HF secret and an accepted model license)",
    )

    xenon_ok = _xenon_checkout_resolves()
    _report(
        problems,
        "xenon checkout (XENON_WORKSPACE_ROOT or ../xenon)",
        xenon_ok,
        "clone https://github.com/concordance-co/xenon next to this repo or set XENON_WORKSPACE_ROOT",
    )

    _summarize(problems)
    return 1 if problems else 0


def _report(problems: list[str], label: str, ok: bool, fix: str) -> None:
    print(f"  [{'ok' if ok else 'MISSING'}] {label}")
    if not ok:
        problems.append(f"{label}: {fix}")


def _summarize(problems: list[str]) -> None:
    if problems:
        print("\nbootstrap incomplete:")
        for problem in problems:
            print(f"  - {problem}")
    else:
        print("\nall Modal resources ready.")


def _modal_authenticated() -> bool:
    if shutil.which("modal") is None:
        return False
    result = subprocess.run(["modal", "profile", "current"], capture_output=True, text=True)
    return result.returncode == 0 and bool(result.stdout.strip())


def _volume_exists(name: str) -> bool:
    result = subprocess.run(["modal", "volume", "ls", name], capture_output=True, text=True)
    return result.returncode == 0


def _secret_exists(name: str) -> bool:
    result = subprocess.run(["modal", "secret", "list"], capture_output=True, text=True)
    return result.returncode == 0 and name in result.stdout


def _model_on_volume(volume: str, model: str) -> bool:
    result = subprocess.run(["modal", "volume", "ls", volume, f"/{model}"], capture_output=True, text=True)
    return result.returncode == 0 and bool(result.stdout.strip())


def _xenon_checkout_resolves() -> bool:
    from pathlib import Path

    from backend.paths import REPO_ROOT

    configured = env_value("XENON_WORKSPACE_ROOT")
    candidate = Path(configured).expanduser() if configured else REPO_ROOT.parent / "xenon"
    return (candidate / "pipelines_v2").is_dir()


def _download_model(model: str) -> None:
    """Run a CPU Modal function that snapshots the model onto the volume."""

    import modal

    app = modal.App("persona-audit-bootstrap")
    volume = modal.Volume.from_name(model_volume_name(), create_if_missing=True)
    image = modal.Image.debian_slim().pip_install("huggingface_hub[hf_transfer]")

    @app.function(
        image=image,
        volumes={MODEL_VOLUME_PATH: volume},
        secrets=[modal.Secret.from_name(hf_secret_name())],
        timeout=DOWNLOAD_TIMEOUT_SECONDS,
        cpu=8,
        memory=16 * 1024,
    )
    def snapshot(model_ref: str) -> str:
        import os

        from huggingface_hub import snapshot_download

        os.environ.setdefault("HF_HUB_ENABLE_HF_TRANSFER", "1")
        target = f"{MODEL_VOLUME_PATH}/{model_ref}"
        snapshot_download(repo_id=model_ref, local_dir=target, token=os.environ.get("HF_TOKEN"))
        volume.commit()
        return target

    with app.run():
        target = snapshot.remote(model)
        print(f"model downloaded to {target}")


if __name__ == "__main__":
    sys.exit(main())
