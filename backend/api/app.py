"""FastAPI backend for Persona Audit."""

from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from backend.api.audit_data import (
    audit_report_overview,
    audit_session,
    audit_sessions,
    audit_user,
    audit_users,
    product_analytics_report,
)
from backend.api.character import character_report, character_trait_detail
from backend.api.hermes import hermes_overview
from backend.api.tail import tail_report
from backend.api.scoring_spaces import scoring_readiness
from backend.api.catalog import (
    behavior_assets,
    emotion_payload,
    high_stakes_report,
    high_stakes_reports,
    product_overview,
)
from backend.api.trace_source import load_product_traces


app = FastAPI(title="Persona Audit")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "persona-audit"}


@app.get("/api/overview")
async def overview() -> dict:
    return product_overview()


@app.get("/api/assets")
async def assets() -> list[dict]:
    return behavior_assets()


@app.get("/api/audit/report")
async def audit_report_detail(provider: str | None = None) -> dict:
    return audit_report_overview(provider=provider)


@app.get("/api/audit/product-analytics")
async def audit_product_analytics(provider: str | None = None) -> dict:
    return product_analytics_report(provider=provider)


@app.get("/api/audit/sessions")
async def audit_session_index(domain: str | None = None, risk: str | None = None, provider: str | None = None) -> list[dict]:
    return audit_sessions(domain=domain, risk=risk, provider=provider)


@app.get("/api/audit/sessions/{trace_id}")
async def audit_session_detail(trace_id: str, provider: str | None = None) -> dict:
    session = audit_session(trace_id, provider=provider)
    if session is None:
        raise HTTPException(status_code=404, detail="session not found")
    return session


@app.get("/api/audit/users")
async def audit_user_index(provider: str | None = None) -> list[dict]:
    return audit_users(provider=provider)


@app.get("/api/audit/users/{user_id}")
async def audit_user_detail(user_id: str, provider: str | None = None) -> dict:
    user = audit_user(user_id, provider=provider)
    if user is None:
        raise HTTPException(status_code=404, detail="user not found")
    return user


@app.get("/api/audit/character")
async def audit_character(provider: str | None = None) -> dict:
    return character_report(provider=provider)


@app.get("/api/audit/character/{coordinate}")
async def audit_character_trait(coordinate: str, provider: str | None = None) -> dict:
    detail = character_trait_detail(coordinate, provider=provider)
    if detail is None:
        raise HTTPException(status_code=404, detail="trait not found")
    return detail


@app.get("/api/audit/tail")
async def audit_tail(provider: str | None = None) -> dict:
    return tail_report(provider=provider)


@app.get("/api/audit/score-spaces")
async def audit_score_spaces(provider: str | None = None) -> dict:
    traces, provider_id, source = load_product_traces(provider)
    return scoring_readiness(traces=traces, provider_id=provider_id, source=source)


@app.get("/api/hermes/overview")
async def hermes_mode_overview() -> dict:
    return hermes_overview()


@app.get("/api/emotions")
async def emotions() -> dict:
    return emotion_payload()


@app.get("/api/high-stakes/reports")
async def high_stakes_report_index() -> list[dict]:
    return high_stakes_reports()


@app.get("/api/high-stakes/reports/{report_id}")
async def high_stakes_report_detail(report_id: str) -> dict:
    report = high_stakes_report(report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="report not found")
    return report
