"""Shared filesystem and environment helpers for Persona Audit.

Environment naming: the supported prefix is ``PERSONA_AUDIT_``. The older
``BEHAVIOR_AUDIT_`` prefix (and ``XENON_NEON_DATABASE_URL`` for the database
URL) still works as a deprecated alias — always read env vars through
:func:`env_value` so the fallback and deprecation warning apply everywhere.
"""

from __future__ import annotations

import os
import warnings
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent
REPO_ROOT = PACKAGE_ROOT.parent
DATA_ROOT = REPO_ROOT / "data"
REPORT_ROOT = REPO_ROOT / "reports"
FRONTEND_ROOT = REPO_ROOT / "frontend"
DOTENV_PATH = REPO_ROOT / ".env"

ENV_PREFIX = "PERSONA_AUDIT_"
LEGACY_ENV_PREFIX = "BEHAVIOR_AUDIT_"
DATABASE_URL_ENV = "PERSONA_AUDIT_DATABASE_URL"
LEGACY_NEON_DATABASE_URL_ENV = "XENON_NEON_DATABASE_URL"

_WARNED_LEGACY_ENV: set[str] = set()


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


def _legacy_names(name: str) -> tuple[str, ...]:
    """Deprecated alias env names for a PERSONA_AUDIT_* variable."""

    legacy: list[str] = []
    if name.startswith(ENV_PREFIX):
        legacy.append(LEGACY_ENV_PREFIX + name.removeprefix(ENV_PREFIX))
    if name == DATABASE_URL_ENV:
        legacy.append(LEGACY_NEON_DATABASE_URL_ENV)
    return tuple(legacy)


def env_value(name: str, default: str | None = None) -> str | None:
    """Read an env var, honoring deprecated BEHAVIOR_AUDIT_* aliases.

    Resolution order: ``.env`` is loaded (non-overriding), then the canonical
    ``PERSONA_AUDIT_*`` name wins, then each legacy alias (with a once-per-name
    DeprecationWarning), then ``default``. Empty strings count as unset.
    """

    load_dotenv()
    value = os.environ.get(name)
    if value:
        return value
    for legacy_name in _legacy_names(name):
        value = os.environ.get(legacy_name)
        if value:
            if legacy_name not in _WARNED_LEGACY_ENV:
                _WARNED_LEGACY_ENV.add(legacy_name)
                warnings.warn(
                    f"{legacy_name} is deprecated; set {name} instead",
                    DeprecationWarning,
                    stacklevel=2,
                )
            return value
    return default


def configured_database_url(env_var: str = DATABASE_URL_ENV) -> str | None:
    """Return the configured Postgres-compatible database URL.

    ``PERSONA_AUDIT_DATABASE_URL`` is the public-facing name. The deprecated
    ``BEHAVIOR_AUDIT_DATABASE_URL`` and ``XENON_NEON_DATABASE_URL`` names
    remain supported for older local environments via :func:`env_value`.
    """

    return env_value(env_var)
