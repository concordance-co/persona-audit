"""Shared fixtures for the persona-audit test suite.

The default suite is hermetic: no network, no database, no Modal. Tests that
really execute on Modal live under ``tests/live/`` behind the ``modal_live``
marker (excluded by default via ``addopts`` in ``pyproject.toml``).
"""

from __future__ import annotations

import os

import pytest

from backend.paths import REPO_ROOT

# Pin the tau2 provider to its bundled smoke fixture so the suite behaves
# identically on a fresh clone / CI and on machines that happen to have a
# sibling tau2-bench checkout (which the loader would otherwise pick up).
os.environ.setdefault("PERSONA_AUDIT_TAU2_PROVIDER", "tau2_smoke")


@pytest.fixture(scope="session")
def repo_root():
    return REPO_ROOT
