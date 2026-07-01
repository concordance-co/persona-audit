from __future__ import annotations

import re
from pathlib import Path

from backend.api.app import app
from backend.paths import DATA_ROOT, FRONTEND_ROOT, REPO_ROOT, configured_database_url


EXPECTED_ENV_EXAMPLE_KEYS = {
    "BEHAVIOR_AUDIT_DATABASE_URL",
    "XENON_NEON_DATABASE_URL",
    "HF_TOKEN",
    "BEHAVIOR_AUDIT_PROVIDER",
    "BEHAVIOR_AUDIT_DEFAULT_PROVIDER",
    "BEHAVIOR_AUDIT_TRACE_SOURCE",
    "BEHAVIOR_AUDIT_TRACE_TABLE",
    "BEHAVIOR_AUDIT_TURN_TABLE",
    "BEHAVIOR_AUDIT_TAU2_PROVIDER",
    "BEHAVIOR_AUDIT_TAU2_RESULTS",
    "BEHAVIOR_AUDIT_SCORE_RUN_ID",
    "BEHAVIOR_AUDIT_SCORE_TABLE",
    "BEHAVIOR_AUDIT_SCORE_SUMMARY_TABLE",
    "BEHAVIOR_AUDIT_SCORE_SUMMARY_CACHE",
    "BEHAVIOR_AUDIT_TAU2_SCORE_LIMIT",
    "BEHAVIOR_AUDIT_TAU2_CAPTURE_GPU",
    "BEHAVIOR_AUDIT_TAU2_CAPTURE_TIMEOUT",
    "BEHAVIOR_AUDIT_TAU2_CAPTURE_MAX_CONTAINERS",
    "BEHAVIOR_AUDIT_TAU2_CAPTURE_SHARDS",
    "BEHAVIOR_AUDIT_TAU2_ANALYSIS_TIMEOUT",
    "BEHAVIOR_AUDIT_TAU2_MAX_MODEL_LEN",
    "BEHAVIOR_AUDIT_TAU2_TENSOR_PARALLEL_SIZE",
    "BEHAVIOR_AUDIT_TAU2_GPU_MEMORY_UTILIZATION",
    "BEHAVIOR_AUDIT_TAU2_ENFORCE_EAGER",
    "BEHAVIOR_AUDIT_TAU2_MAX_NUM_SEQS",
    "BEHAVIOR_AUDIT_TAU2_MAX_NUM_BATCHED_TOKENS",
}

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


def test_env_example_documents_runtime_env_surface() -> None:
    env_example = REPO_ROOT / ".env.example"
    keys = {
        match.group(1)
        for line in env_example.read_text(encoding="utf-8").splitlines()
        if (match := re.match(r"^([A-Z0-9_]+)=", line))
    }

    assert EXPECTED_ENV_EXAMPLE_KEYS.issubset(keys)


def test_database_url_prefers_public_env_and_keeps_legacy_fallback(monkeypatch) -> None:
    monkeypatch.delenv("BEHAVIOR_AUDIT_DATABASE_URL", raising=False)
    monkeypatch.setenv("XENON_NEON_DATABASE_URL", "postgresql://legacy")

    assert configured_database_url() == "postgresql://legacy"

    monkeypatch.setenv("BEHAVIOR_AUDIT_DATABASE_URL", "postgresql://public")

    assert configured_database_url() == "postgresql://public"


def test_public_api_route_inventory_is_stable() -> None:
    routes = {route.path for route in app.routes if route.path.startswith("/api/")}

    assert EXPECTED_API_ROUTES.issubset(routes)


def test_bundled_artifact_paths_exist_for_local_dashboard() -> None:
    expected_paths = [
        DATA_ROOT / "neon_score_summaries",
        DATA_ROOT / "supplemental_scores",
        REPO_ROOT / "reports/behavior_audit_public",
        FRONTEND_ROOT / "dist/index.html",
    ]

    for path in expected_paths:
        assert path.exists(), path
