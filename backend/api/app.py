"""FastAPI backend for Persona Audit.

Routes are deliberately plain ``def`` (not ``async def``): every handler does
blocking work (psycopg queries, JSON file reads), and FastAPI runs sync
endpoints on its threadpool, which keeps the event loop responsive. Do not
convert them to ``async def`` without also moving the blocking IO off-loop.

View-model results are memoized (see backend.api.cache); after uploading new
data, POST /api/cache/clear or restart the process.
"""

from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from backend.api import cache
from backend.api.audit_data import (
    audit_report_overview,
    audit_session,
    audit_sessions,
    audit_user,
    audit_users,
    product_analytics_report,
)
from backend.api.catalog import (
    behavior_assets,
    emotion_payload,
    high_stakes_report,
    high_stakes_reports,
    product_overview,
)
from backend.api.character import character_report, character_trait_detail
from backend.api.db import configured_database_url
from backend.api.hermes import hermes_overview
from backend.api.registry import resolve_provider
from backend.api.scores import score_inventory
from backend.api.scoring_spaces import scoring_readiness
from backend.api.tail import tail_report
from backend.api.trace_source import load_product_traces
from backend.paths import env_value

app = FastAPI(title="Persona Audit")


def _cors_origins() -> list[str]:
    # Local-first dashboard: wide-open by default. Set a comma-separated
    # PERSONA_AUDIT_CORS_ORIGINS for shared deployments.
    configured = env_value("PERSONA_AUDIT_CORS_ORIGINS", "*")
    return [origin.strip() for origin in configured.split(",") if origin.strip()]


_origins = _cors_origins()
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    # Wildcard origins with credentials is an invalid CORS combination;
    # only allow credentials when explicit origins are configured.
    allow_credentials=_origins != ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health(provider: str | None = None) -> dict:
    """Liveness plus self-diagnosis: where traces and scores come from."""

    selected = resolve_provider(provider)
    traces, provider_id, source = load_product_traces(selected)
    inventory = score_inventory(provider=selected)
    return {
        "status": "ok",
        "service": "persona-audit",
        "provider": selected,
        "trace_source": {"provider_id": provider_id, "label": source, "trace_count": len(traces)},
        "score_source": {
            "database_configured": bool(configured_database_url()),
            "available": bool(inventory.get("available")),
            "run_id": inventory.get("run_id"),
        },
    }


@app.post("/api/cache/clear")
def cache_clear() -> dict:
    """Invalidate all memoized report/score view-models (e.g. after an upload)."""

    return {"cleared": cache.clear_all()}


@app.get("/api/overview")
def overview() -> dict:
    return product_overview()


@app.get("/api/assets")
def assets() -> list[dict]:
    return behavior_assets()


@app.get("/api/audit/report")
def audit_report_detail(provider: str | None = None) -> dict:
    return audit_report_overview(provider=provider)


@app.get("/api/audit/product-analytics")
def audit_product_analytics(provider: str | None = None) -> dict:
    return product_analytics_report(provider=provider)


@app.get("/api/audit/sessions")
def audit_session_index(domain: str | None = None, risk: str | None = None, provider: str | None = None) -> list[dict]:
    return audit_sessions(domain=domain, risk=risk, provider=provider)


@app.get("/api/audit/sessions/{trace_id}")
def audit_session_detail(trace_id: str, provider: str | None = None) -> dict:
    session = audit_session(trace_id, provider=provider)
    if session is None:
        raise HTTPException(status_code=404, detail="session not found")
    return session


@app.get("/api/audit/users")
def audit_user_index(provider: str | None = None) -> list[dict]:
    return audit_users(provider=provider)


@app.get("/api/audit/users/{user_id}")
def audit_user_detail(user_id: str, provider: str | None = None) -> dict:
    user = audit_user(user_id, provider=provider)
    if user is None:
        raise HTTPException(status_code=404, detail="user not found")
    return user


@app.get("/api/audit/character")
def audit_character(provider: str | None = None) -> dict:
    return character_report(provider=provider)


@app.get("/api/audit/character/{coordinate}")
def audit_character_trait(coordinate: str, provider: str | None = None) -> dict:
    detail = character_trait_detail(coordinate, provider=provider)
    if detail is None:
        raise HTTPException(status_code=404, detail="trait not found")
    return detail


@app.get("/api/audit/tail")
def audit_tail(provider: str | None = None) -> dict:
    return tail_report(provider=provider)


@app.get("/api/audit/score-spaces")
def audit_score_spaces(provider: str | None = None) -> dict:
    traces, provider_id, source = load_product_traces(provider)
    return scoring_readiness(traces=traces, provider_id=provider_id, source=source)


@app.get("/api/hermes/overview")
def hermes_mode_overview() -> dict:
    return hermes_overview()


@app.get("/api/emotions")
def emotions() -> dict:
    return emotion_payload()


@app.get("/api/high-stakes/reports")
def high_stakes_report_index() -> list[dict]:
    return high_stakes_reports()


@app.get("/api/high-stakes/reports/{report_id}")
def high_stakes_report_detail(report_id: str) -> dict:
    report = high_stakes_report(report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="report not found")
    return report
