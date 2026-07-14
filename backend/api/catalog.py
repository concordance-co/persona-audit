"""Catalog helpers for the Persona Audit API."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from backend.api.assistant_traits import audit_assistant_traits
from backend.api.paper_assets import assistant_manifest as load_assistant_manifest
from backend.api.paper_assets import emotion_concepts
from backend.api.paper_assets import emotion_manifest as load_emotion_manifest
from backend.api.scoring_spaces import public_probe_summaries


def product_overview() -> dict[str, Any]:
    assets = behavior_assets()
    high_stakes_steps = public_probe_summaries()
    best_probe = max(
        high_stakes_steps,
        key=lambda item: float(item.get("balanced_accuracy") or 0.0),
        default=None,
    )
    return {
        "product": {
            "name": "Persona Audit",
            "scope": "artifact-backed persona and behavior audit dashboard",
            "sidecar_priority": "deferred",
        },
        "summary": {
            "asset_count": len(assets),
            "high_stakes_report_count": 0,
            "high_stakes_probe_count": len(high_stakes_steps),
            "best_high_stakes_probe": best_probe,
        },
        "signals": assets,
        "high_stakes": {
            "reports": [],
            "metric_rows": high_stakes_steps,
        },
    }


def behavior_assets() -> list[dict[str, Any]]:
    assistant = load_assistant_manifest()
    emotion = load_emotion_manifest()
    emotion_artifacts = _mapping(emotion.get("artifacts"))
    assets = [
        {
            "id": str(_mapping(assistant.get("asset")).get("id")),
            "family": "assistant_axis",
            "label": "Assistant Axis",
            "status": str(_mapping(assistant.get("asset")).get("status")),
            "model": str(_mapping(assistant.get("model")).get("model_id")),
            "layer": int(_mapping(assistant.get("model")).get("target_layer", 0)),
            "artifact": str(_mapping(assistant.get("source")).get("assistant_axis_file")),
            "default_dimensions": list(audit_assistant_traits(assistant)),
            "description": str(_mapping(assistant.get("asset")).get("description")),
        },
        {
            "id": str(_mapping(emotion.get("asset")).get("id")),
            "family": "emotion_vectors",
            "label": "Emotion Vectors",
            "status": str(_mapping(emotion.get("asset")).get("status")),
            "model": str(_mapping(emotion.get("model")).get("model_id")),
            "layer": int(_mapping(emotion.get("model")).get("target_layer", 0)),
            "artifact": str(emotion_artifacts.get("vector_space_artifact_id")),
            "default_dimensions": list(emotion_concepts(mode="pilot", manifest=emotion)),
            "dimension_count": len(emotion_concepts(mode="full", manifest=emotion)),
            "description": str(_mapping(emotion.get("asset")).get("description")),
        },
    ]
    high_stakes = _high_stakes_asset()
    if high_stakes is not None:
        assets.append(high_stakes)
    return assets


def emotion_payload() -> dict[str, Any]:
    manifest = load_emotion_manifest()
    artifacts = _mapping(manifest.get("artifacts"))
    validation = _mapping(manifest.get("validation"))
    return {
        "asset": behavior_assets()[1],
        "concepts": list(emotion_concepts(mode="full", manifest=manifest)),
        "pilot_concepts": list(emotion_concepts(mode="pilot", manifest=manifest)),
        "artifact_paths": {
            "vector_space": artifacts.get("vector_space_path"),
            "geometry": artifacts.get("geometry_path"),
        },
        "validation": {
            "claim": validation.get("claim"),
            "notes": validation.get("notes"),
        },
    }


def high_stakes_reports() -> list[dict[str, Any]]:
    """Return bundled report cards when a public demo archive is selected."""
    return []


def high_stakes_report(report_id: str) -> dict[str, Any] | None:
    return None


def _high_stakes_asset() -> dict[str, Any] | None:
    artifacts = public_probe_summaries()
    if not artifacts:
        return None
    best = max(artifacts, key=lambda item: float(item.get("balanced_accuracy") or 0.0))
    return {
        "id": "high-stakes-interactions-llama-3.3-70b-mean-probe-v1",
        "family": "high_stakes_probe",
        "label": "High-Stakes Probe",
        "status": "persisted_probe_ready",
        "model": "meta-llama/Llama-3.3-70B-Instruct",
        "layer": 31,
        "artifact": "persisted_probe",
        "default_dimensions": ["high-stakes", "low-stakes"],
        "dimension_count": len(artifacts),
        "description": (
            "Persisted full-trace activation probes for high-stakes interaction detection. "
            "Report archives are intentionally not bundled until public demo datasets are selected."
        ),
        "metrics": {
            "best_balanced_accuracy": best.get("balanced_accuracy"),
            "probe_count": len(artifacts),
            "report_count": 0,
        },
    }


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}
