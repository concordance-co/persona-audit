"""Serving hardening: sync routes, cache clearing, health diagnosis, JSON guards."""

from __future__ import annotations

import inspect
import json
import shutil

from fastapi.testclient import TestClient

from backend.api import tau2_loader
from backend.api.app import app
from backend.paths import REPO_ROOT

client = TestClient(app)


def test_routes_are_sync_so_blocking_io_stays_off_the_event_loop() -> None:
    offenders = [
        route.path
        for route in app.routes
        if route.path.startswith("/api/") and inspect.iscoroutinefunction(getattr(route, "endpoint", None))
    ]
    assert not offenders, f"async routes doing blocking IO: {offenders}"


def test_health_reports_trace_and_score_sources() -> None:
    payload = client.get("/api/health", params={"provider": "persona_demo"}).json()
    assert payload["status"] == "ok"
    assert payload["provider"] == "persona_demo"
    assert payload["trace_source"]["trace_count"] == 75
    assert payload["score_source"]["available"] is True
    assert "database_configured" in payload["score_source"]


def test_cache_clear_makes_new_data_visible(monkeypatch, tmp_path) -> None:
    traces_file = tmp_path / "normalized_traces.json"
    shutil.copyfile(REPO_ROOT / "data" / "demo" / "normalized_traces.json", traces_file)
    monkeypatch.setenv("PERSONA_AUDIT_DEMO_PRODUCT_TRACES", str(traces_file))

    cleared = client.post("/api/cache/clear").json()
    assert cleared["cleared"] > 0

    first = client.get("/api/audit/report", params={"provider": "persona_demo"}).json()
    assert first["trace_count"] == 75

    rows = json.loads(traces_file.read_text(encoding="utf-8"))
    traces_file.write_text(json.dumps(rows[:30]), encoding="utf-8")

    stale = client.get("/api/audit/report", params={"provider": "persona_demo"}).json()
    assert stale["trace_count"] == 75, "report should be served from cache until cleared"

    client.post("/api/cache/clear")
    fresh = client.get("/api/audit/report", params={"provider": "persona_demo"}).json()
    assert fresh["trace_count"] == 30

    client.post("/api/cache/clear")


def test_malformed_tau2_results_file_is_skipped_with_warning(tmp_path, caplog) -> None:
    bad = tmp_path / "results.json"
    bad.write_text("{not json", encoding="utf-8")
    payloads = tau2_loader._payloads_from_json(bad)
    assert payloads == []


def test_cors_only_allows_credentials_with_explicit_origins() -> None:
    from backend.api import app as app_module

    assert app_module._origins == ["*"]
    middleware = next(m for m in app.user_middleware if m.cls.__name__ == "CORSMiddleware")
    assert middleware.kwargs["allow_credentials"] is False
