"""Score-summary cache helpers for Persona Audit."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Mapping

from backend.paths import DATA_ROOT, load_dotenv


SCORE_SUMMARY_CACHE_ENV = "BEHAVIOR_AUDIT_SCORE_SUMMARY_CACHE"
SCORE_SUMMARY_CACHE_VERSION = 5
SCORE_SUMMARY_CACHE_DIR = DATA_ROOT / "neon_score_summaries"


def _read_score_summary_cache(run_id: str) -> dict[str, Any] | None:
    path = _score_summary_cache_path(run_id)
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    if payload.get("kind") != "behavior_audit_score_summary":
        return None
    if payload.get("version") != SCORE_SUMMARY_CACHE_VERSION:
        return None
    if payload.get("run_id") != run_id:
        return None
    return payload


def _write_score_summary_cache(summary: Mapping[str, Any]) -> None:
    run_id = str(summary.get("run_id") or "")
    if not run_id:
        return
    path = _score_summary_cache_path(run_id)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = path.with_name(f"{path.name}.tmp")
        tmp_path.write_text(json.dumps(summary, sort_keys=True, separators=(",", ":")), encoding="utf-8")
        tmp_path.replace(path)
    except OSError:
        return


def _score_summary_cache_path(run_id: str) -> Path:
    load_dotenv()
    configured = os.environ.get(SCORE_SUMMARY_CACHE_ENV)
    if configured:
        path = Path(configured).expanduser()
        return path if path.suffix else path / f"{_safe_cache_name(run_id)}.json"
    return SCORE_SUMMARY_CACHE_DIR / f"{_safe_cache_name(run_id)}.json"


def _safe_cache_name(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in {"-", "_", "."} else "_" for ch in value)


__all__ = [
    "SCORE_SUMMARY_CACHE_DIR",
    "SCORE_SUMMARY_CACHE_ENV",
    "SCORE_SUMMARY_CACHE_VERSION",
    "_read_score_summary_cache",
    "_score_summary_cache_path",
    "_write_score_summary_cache",
]
