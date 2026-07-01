"""Shared filesystem and environment helpers for Persona Audit."""

from __future__ import annotations

import os
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent
REPO_ROOT = PACKAGE_ROOT.parent
DATA_ROOT = REPO_ROOT / "data"
REPORT_ROOT = REPO_ROOT / "reports"
FRONTEND_ROOT = REPO_ROOT / "frontend"
DOTENV_PATH = REPO_ROOT / ".env"
DATABASE_URL_ENV = "BEHAVIOR_AUDIT_DATABASE_URL"
LEGACY_DATABASE_URL_ENV = "XENON_NEON_DATABASE_URL"


def load_dotenv(path: str | Path = DOTENV_PATH) -> None:
    """Load simple KEY=VALUE lines without overriding existing environment values."""

    dotenv_path = Path(path)
    if not dotenv_path.exists():
        return
    for line in dotenv_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        key = key.strip()
        if key and key not in os.environ:
            os.environ[key] = value.strip().strip('"').strip("'")


def configured_database_url(env_var: str = DATABASE_URL_ENV) -> str | None:
    """Return the configured Postgres-compatible database URL.

    ``BEHAVIOR_AUDIT_DATABASE_URL`` is the public-facing name. The legacy
    ``XENON_NEON_DATABASE_URL`` name remains supported for older
    local environments.
    """

    load_dotenv()
    value = os.environ.get(env_var)
    if value:
        return value
    if env_var == DATABASE_URL_ENV:
        return os.environ.get(LEGACY_DATABASE_URL_ENV)
    return None
