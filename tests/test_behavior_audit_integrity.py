from __future__ import annotations

from fastapi.testclient import TestClient

from backend.api.app import app


client = TestClient(app)


def test_core_audit_endpoints_keep_public_shapes() -> None:
    checks = {
        "/api/audit/report": {"kind", "dataset_name", "provider", "trace_count", "modules", "overview", "summary"},
        "/api/audit/product-analytics": {"kind", "dataset_name", "provider", "trace_count", "persona_overview", "summary"},
        "/api/audit/sessions": None,
        "/api/audit/users": None,
        "/api/audit/character": {"points", "dropped", "meta"},
        "/api/audit/tail": {"modes", "scatter", "meta"},
        "/api/audit/score-spaces": {"provider", "xenon_input", "capture_plan", "spaces"},
    }

    for path, expected_keys in checks.items():
        response = client.get(path)
        assert response.status_code == 200, path
        payload = response.json()
        if expected_keys is None:
            assert isinstance(payload, list), path
            assert payload, path
        else:
            assert expected_keys.issubset(payload), path
