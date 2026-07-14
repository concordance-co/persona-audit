"""Guards for the live Modal tier: double opt-in plus infrastructure preflight.

These tests execute real GPU workloads on Modal (roughly $5-20 per full
session including cold starts). They only run when BOTH are true:

1. selected explicitly: ``pytest -m modal_live`` (excluded by default via
   ``addopts`` in pyproject.toml), and
2. ``PERSONA_AUDIT_LIVE_TESTS=1`` is set.

Before anything runs, ``bootstrap_modal --check`` verifies Modal auth, the
model/data volumes, the HF secret, the model weights, and the xenon checkout,
failing fast with actionable messages (see backend/scripts/bootstrap_modal.py).
"""

from __future__ import annotations

import subprocess
import sys

import pytest

from backend.paths import REPO_ROOT, env_value

WRAPPER = REPO_ROOT / "backend" / "scripts" / "run_xenon_workflow.sh"


@pytest.fixture(scope="session", autouse=True)
def live_guard():
    if env_value("PERSONA_AUDIT_LIVE_TESTS") != "1":
        pytest.skip("live Modal tests need PERSONA_AUDIT_LIVE_TESTS=1 (they cost real GPU money)")
    check = subprocess.run(
        [sys.executable, "-m", "backend.scripts.bootstrap_modal", "--check"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    if check.returncode != 0:
        pytest.fail(f"Modal infrastructure not ready:\n{check.stdout}\n{check.stderr}", pytrace=False)


def run_workflow(workflow_file: str, extra_env: dict[str, str] | None = None, timeout: int = 3600) -> dict:
    """Run a workflow via the wrapper; returns the CLI's JSON result payload."""

    import json
    import os

    env = {**os.environ, **(extra_env or {})}
    result = subprocess.run(
        [str(WRAPPER), "run", "--file", workflow_file, "--logging", "INFO"],
        cwd=REPO_ROOT,
        env=env,
        stdout=subprocess.PIPE,
        text=True,
        timeout=timeout,
    )
    if result.returncode != 0:
        pytest.fail(
            f"workflow run failed for {workflow_file} (exit {result.returncode}).\n"
            f"stdout tail:\n{result.stdout[-2000:]}\n"
            f"Inspect with: {WRAPPER} show --file {workflow_file} --latest",
            pytrace=False,
        )
    return json.loads(result.stdout)
