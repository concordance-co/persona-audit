"""Repo hygiene invariants: env-var documentation, route stability, tracked artifacts."""

from __future__ import annotations

import re
import subprocess
import warnings

from backend.api.app import app
from backend.paths import DATA_ROOT, REPO_ROOT, configured_database_url, env_value

EXPECTED_API_ROUTES = {
    "/api/health",
    "/api/overview",
    "/api/assets",
    "/api/audit/report",
    "/api/audit/product-analytics",
    "/api/audit/sessions",
    "/api/audit/sessions/{trace_id}",
    "/api/audit/users",
    "/api/audit/users/{user_id}",
    "/api/audit/character",
    "/api/audit/character/{coordinate}",
    "/api/audit/tail",
    "/api/audit/score-spaces",
    "/api/emotions",
    "/api/high-stakes/reports",
    "/api/high-stakes/reports/{report_id}",
}


def _env_example_keys() -> set[str]:
    env_example = REPO_ROOT / ".env.example"
    return {
        match.group(1)
        for line in env_example.read_text(encoding="utf-8").splitlines()
        if (match := re.match(r"^([A-Z0-9_]+)=", line))
    }


def test_env_example_documents_every_env_var_read_by_backend() -> None:
    """Every PERSONA_AUDIT_* literal in backend/factory code must appear in .env.example.

    This scan replaces a hand-maintained key list, so newly introduced env vars
    fail loudly until they are documented.
    """

    read_vars: set[str] = set()
    for package in ("backend", "factory"):
        for path in (REPO_ROOT / package).rglob("*.py"):
            read_vars.update(re.findall(r'"(PERSONA_AUDIT_[A-Z0-9_]+)"', path.read_text(encoding="utf-8")))

    missing = read_vars - _env_example_keys()
    assert not missing, f"env vars read in backend but undocumented in .env.example: {sorted(missing)}"


def test_env_example_uses_only_supported_prefix() -> None:
    legacy = {key for key in _env_example_keys() if key.startswith("BEHAVIOR_AUDIT_")}
    assert not legacy, f".env.example must document PERSONA_AUDIT_* names, found: {sorted(legacy)}"


def test_database_url_prefers_public_env_and_keeps_legacy_fallbacks(monkeypatch) -> None:
    for name in ("PERSONA_AUDIT_DATABASE_URL", "BEHAVIOR_AUDIT_DATABASE_URL", "XENON_NEON_DATABASE_URL"):
        monkeypatch.delenv(name, raising=False)

    monkeypatch.setenv("XENON_NEON_DATABASE_URL", "postgresql://legacy-neon")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        assert configured_database_url() == "postgresql://legacy-neon"

    monkeypatch.setenv("BEHAVIOR_AUDIT_DATABASE_URL", "postgresql://legacy-behavior")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        assert configured_database_url() == "postgresql://legacy-behavior"

    monkeypatch.setenv("PERSONA_AUDIT_DATABASE_URL", "postgresql://public")
    assert configured_database_url() == "postgresql://public"


def test_legacy_env_alias_warns_deprecation(monkeypatch) -> None:
    import backend.paths as paths

    monkeypatch.delenv("PERSONA_AUDIT_TRACE_SOURCE", raising=False)
    monkeypatch.setenv("BEHAVIOR_AUDIT_TRACE_SOURCE", "local")
    monkeypatch.setattr(paths, "_WARNED_LEGACY_ENV", set())

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        assert env_value("PERSONA_AUDIT_TRACE_SOURCE") == "local"

    assert any(issubclass(w.category, DeprecationWarning) for w in caught)


def test_public_api_route_inventory_is_stable() -> None:
    routes = {route.path for route in app.routes if route.path.startswith("/api/")}

    assert EXPECTED_API_ROUTES.issubset(routes)


def test_bundled_artifact_paths_exist_for_local_dashboard() -> None:
    expected_paths = [
        DATA_ROOT / "score_summaries",
        DATA_ROOT / "supplemental_scores",
        REPO_ROOT / "reports/behavior_audit_public",
    ]

    for path in expected_paths:
        assert path.exists(), path


def test_frontend_dist_is_not_tracked() -> None:
    tracked = subprocess.run(
        ["git", "ls-files", "frontend/dist"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()

    assert tracked == "", "frontend/dist is a build output and must stay untracked"
