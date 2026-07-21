"""Scoring-space readiness for normalized behavior-audit traces."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from backend.api.assistant_traits import audit_assistant_traits
from backend.api.models import AuditTrace, AuditTurn
from backend.api.paper_assets import assistant_manifest as load_assistant_manifest
from backend.api.paper_assets import emotion_concepts
from backend.api.paper_assets import emotion_manifest as load_emotion_manifest
from backend.api.registry import provider_descriptor


def _show_high_stakes(provider_id: str) -> bool:
    features = provider_descriptor(provider_id).get("features") or {}
    return bool(features.get("show_high_stakes"))


HIGH_STAKES_PERSISTED_PROBES: tuple[dict[str, Any], ...] = (
    {
        "domain": "synthetic_test",
        "probe_family": "generic_mean_probe",
        "artifact_id": "probe_1_bfdeeb8f",
        "capture_artifact_id": "capture_1_aaec534d629e",
        "source_run_id": "wr_74ad66b453f2_c5894ad0",
        "balanced_accuracy": 0.9655,
        "training_mode": "fixed_train_values",
        "target_root": "/data/artifacts/high_stakes_interactions_persisted_probes_v1",
        "status": "audit_ready",
    },
    {
        "domain": "anthropic_hh_balanced",
        "probe_family": "generic_mean_probe",
        "artifact_id": "probe_1_c31121f4",
        "source_artifact_id": "probe_1_f2c02739",
        "capture_artifact_id": "capture_1_aaec534d629e",
        "source_run_id": "wr_74ad66b453f2_c5894ad0",
        "balanced_accuracy": 0.8043,
        "training_mode": "fixed_train_values",
        "target_root": "/data/artifacts/high_stakes_interactions_persisted_probes_v1",
        "status": "audit_ready",
    },
    {
        "domain": "mt_balanced",
        "probe_family": "generic_mean_probe",
        "artifact_id": "probe_1_84281953",
        "source_artifact_id": "probe_1_585c4164",
        "capture_artifact_id": "capture_1_aaec534d629e",
        "source_run_id": "wr_74ad66b453f2_c5894ad0",
        "balanced_accuracy": 0.793,
        "training_mode": "fixed_train_values",
        "target_root": "/data/artifacts/high_stakes_interactions_persisted_probes_v1",
        "status": "audit_ready",
    },
    {
        "domain": "mts_balanced",
        "probe_family": "generic_mean_probe",
        "artifact_id": "probe_1_38cac2e9",
        "capture_artifact_id": "capture_1_aaec534d629e",
        "source_run_id": "wr_74ad66b453f2_c5894ad0",
        "balanced_accuracy": 0.9651,
        "training_mode": "fixed_train_values",
        "target_root": "/data/artifacts/high_stakes_interactions_persisted_probes_v1",
        "status": "audit_ready",
    },
    {
        "domain": "finance_cfpb",
        "probe_family": "generic_mean_probe",
        "artifact_id": "probe_1_b0a85399",
        "source_artifact_id": "probe_1_3681b4aa",
        "capture_artifact_id": "capture_1_c1ef15020dbe",
        "source_run_id": "wr_e63da1633700_dd3d1edb",
        "balanced_accuracy": 0.9167,
        "training_mode": "fixed_train_values",
        "target_root": "/data/artifacts/high_stakes_interactions_persisted_probes_v1",
        "status": "audit_ready",
    },
    {
        "domain": "finance_cfpb",
        "probe_family": "finance_baseline_mean_probe",
        "artifact_id": "probe_1_f625de85",
        "source_artifact_id": "probe_1_2068b200",
        "capture_artifact_id": "capture_1_c1ef15020dbe",
        "source_run_id": "wr_e403ca9a78d4_152b073f",
        "balanced_accuracy": 0.9167,
        "training_mode": "fixed_train_values",
        "target_root": "/data/artifacts/high_stakes_interactions_persisted_probes_v1",
        "status": "audit_ready",
    },
    {
        "domain": "anthropic_hh_balanced",
        "probe_family": "domain_adapted_probe",
        "artifact_id": "probe_1_2206e4b9",
        "source_artifact_id": "probe_1_d5db08b3",
        "capture_artifact_id": "capture_1_a46eecad6ee1",
        "source_run_id": "wr_47486cc1a90a_98810de3",
        "balanced_accuracy": 0.9393,
        "training_mode": "staged_finetune",
        "train_stages": [["synthetic_train"], ["dev_anthropic_hh_balanced"]],
        "stage_epochs": [1, 12],
        "target_root": "/data/artifacts/high_stakes_interactions_persisted_probes_v2",
        "status": "audit_ready",
    },
    {
        "domain": "mt_balanced",
        "probe_family": "domain_adapted_probe",
        "artifact_id": "probe_1_4fb322bc",
        "source_artifact_id": "probe_1_c457ba1f",
        "capture_artifact_id": "capture_1_a46eecad6ee1",
        "source_run_id": "wr_47486cc1a90a_98810de3",
        "balanced_accuracy": 0.8626,
        "training_mode": "staged_finetune",
        "train_stages": [["synthetic_train"], ["dev_mt_balanced"]],
        "stage_epochs": [1, 12],
        "target_root": "/data/artifacts/high_stakes_interactions_persisted_probes_v2",
        "status": "audit_ready",
    },
    {
        "domain": "mts_balanced",
        "probe_family": "domain_adapted_probe",
        "artifact_id": "probe_1_a0e26444",
        "source_artifact_id": "probe_1_f7000486",
        "capture_artifact_id": "capture_1_a46eecad6ee1",
        "source_run_id": "wr_47486cc1a90a_98810de3",
        "balanced_accuracy": 0.9767,
        "training_mode": "staged_finetune",
        "train_stages": [["synthetic_train"], ["dev_mts_balanced"]],
        "stage_epochs": [1, 12],
        "target_root": "/data/artifacts/high_stakes_interactions_persisted_probes_v2",
        "status": "audit_ready",
    },
    {
        "domain": "toolace_balanced",
        "probe_family": "domain_adapted_probe",
        "artifact_id": "probe_1_42149475",
        "source_artifact_id": "probe_1_d9a1337c",
        "capture_artifact_id": "capture_1_a46eecad6ee1",
        "source_run_id": "wr_47486cc1a90a_98810de3",
        "balanced_accuracy": 0.8134,
        "training_mode": "staged_finetune",
        "train_stages": [["synthetic_train"], ["dev_toolace_balanced"]],
        "stage_epochs": [1, 12],
        "target_root": "/data/artifacts/high_stakes_interactions_persisted_probes_v2",
        "status": "audit_ready",
    },
    {
        "domain": "mental_health_balanced",
        "probe_family": "domain_adapted_probe",
        "artifact_id": "probe_1_167a0b0d",
        "source_artifact_id": "probe_1_457bb296",
        "capture_artifact_id": "capture_1_a46eecad6ee1",
        "source_run_id": "wr_47486cc1a90a_98810de3",
        "balanced_accuracy": 0.9514,
        "training_mode": "staged_finetune",
        "train_stages": [["synthetic_train"], ["dev_mental_health_balanced_exploratory"]],
        "stage_epochs": [1, 12],
        "target_root": "/data/artifacts/high_stakes_interactions_persisted_probes_v2",
        "status": "audit_ready",
    },
    {
        "domain": "aya_redteaming_balanced",
        "probe_family": "domain_adapted_probe",
        "artifact_id": "probe_1_b709e5ad",
        "source_artifact_id": "probe_1_6a2c7c70",
        "capture_artifact_id": "capture_1_a46eecad6ee1",
        "source_run_id": "wr_47486cc1a90a_98810de3",
        "balanced_accuracy": 0.8642,
        "training_mode": "staged_finetune",
        "train_stages": [["synthetic_train"], ["dev_aya_redteaming_balanced_exploratory"]],
        "stage_epochs": [1, 12],
        "target_root": "/data/artifacts/high_stakes_interactions_persisted_probes_v2",
        "status": "audit_ready",
    },
    {
        "domain": "finance_cfpb",
        "probe_family": "domain_adapted_probe",
        "artifact_id": "probe_1_bb998787",
        "source_artifact_id": "probe_1_7557d1bf",
        "capture_artifact_id": "capture_1_c1ef15020dbe",
        "source_run_id": "wr_e403ca9a78d4_152b073f",
        "balanced_accuracy": 0.9667,
        "training_mode": "staged_finetune",
        "train_stages": [["synthetic_train"], ["dev_finance_cfpb"]],
        "stage_epochs": [1, 12],
        "target_root": "/data/artifacts/high_stakes_interactions_persisted_probes_v2",
        "status": "audit_ready",
    },
)


_PUBLIC_PROBE_FIELDS = (
    "domain",
    "probe_family",
    "balanced_accuracy",
    "training_mode",
    "train_stages",
    "stage_epochs",
    "status",
)


def public_probe_summaries() -> list[dict[str, Any]]:
    """Probe metadata safe for API payloads.

    ``HIGH_STAKES_PERSISTED_PROBES`` carries workflow-side provenance (run ids,
    artifact ids, Modal volume paths) that scoring steps need but API consumers
    do not; only the methodology fields are exposed here.
    """

    return [
        {field: artifact[field] for field in _PUBLIC_PROBE_FIELDS if field in artifact}
        for artifact in HIGH_STAKES_PERSISTED_PROBES
    ]


def scoring_readiness(
    *,
    traces: Sequence[AuditTrace],
    provider_id: str,
    source: str,
) -> dict[str, Any]:
    records = trace_scoring_records(traces)
    return {
        "provider": {
            "id": provider_id,
            "source": source,
            "trace_count": len(traces),
            "assistant_turn_record_count": len(records),
            "domains": sorted({trace.domain for trace in traces}),
            "source_models": sorted({trace.source_model for trace in traces}),
            "user_models": sorted({trace.user_model for trace in traces}),
        },
        "capture_input": {
            "record_count": len(records),
            "record_kind": "assistant_turn_trace",
            "sample_records": records[:3],
        },
        "capture_plan": {
            "model_id": "meta-llama/Llama-3.3-70B-Instruct",
            "residual_site": "resid_post",
            "required_layers": [31, 40, 52],
            "sections": ["assistant_response", "full_trace"],
            "note": (
                "Assistant Axis/traits and emotions can share one response-residual capture "
                "if layers 40 and 52 are included. The high-stakes probes use full-trace "
                "features at layer 31 and now point at persisted probe payloads on Modal."
            ),
        },
        "spaces": [
            _assistant_axis_space(provider_id=provider_id),
            _emotion_space(),
            *([_high_stakes_probe_space()] if _show_high_stakes(provider_id) else []),
        ],
    }


def trace_scoring_records(traces: Sequence[AuditTrace]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for trace in traces:
        prefix: list[AuditTurn] = []
        assistant_index = 0
        for turn in trace.turns:
            prefix.append(turn)
            if turn.role != "assistant":
                continue
            # Tool-call-only assistant turns (real Hermes sessions and the
            # bundled hermes demo both have them) have no visible response:
            # their span would map to zero tokens and abort the capture run.
            # They still appear in the rendered context of later turns.
            if not turn.content.strip():
                continue
            text, span, reasoning_span = _render_trace_with_span(prefix, target_turn=turn)
            metadata = {
                "source_model": trace.source_model,
                "user_model": trace.user_model,
                "source": trace.metadata.get("source"),
                "workflow": trace.metadata.get("workflow"),
                "final_action": trace.metadata.get("final_action"),
                "started_at": trace.metadata.get("started_at"),
                "ended_at": trace.metadata.get("ended_at"),
            }
            if reasoning_span is not None:
                metadata["assistant_reasoning"] = reasoning_span
            records.append(
                {
                    "example_id": f"{trace.trace_id}__assistant_{assistant_index:03d}",
                    "trace_id": trace.trace_id,
                    "turn_index": turn.index,
                    "text": text,
                    "assistant_response": span,
                    "labels": {
                        "domain": trace.domain,
                        "task_id": trace.task_id,
                        "outcome": trace.outcome,
                        "reward": trace.reward,
                        "is_high_stakes_candidate": bool(trace.labels.get("is_high_stakes_candidate")),
                    },
                    "metadata": metadata,
                }
            )
            assistant_index += 1
    return records


def _assistant_axis_space(*, provider_id: str = "tau2") -> dict[str, Any]:
    manifest = load_assistant_manifest()
    asset = _mapping(manifest.get("asset"))
    model = _mapping(manifest.get("model"))
    traits = list(audit_assistant_traits(manifest))
    return {
        "id": str(asset.get("id")),
        "family": "assistant_axis",
        "label": "Assistant Axis + released traits",
        "status": "workflow_ready",
        "score_kind": "projection",
        "model": model.get("model_id"),
        "layer": int(model.get("target_layer", 40)),
        "coordinate_count": 1 + len(traits),
        "coordinates": ["assistant_axis", *[f"assistant_axis_trait__{trait}" for trait in traits]],
        "pipeline_specs": [
            "AssistantAxisPrecomputedCoordinateSpec",
            "AssistantAxisTraitCoordinateSpec",
            "ProjectionSpec",
        ],
        "requires": ["HF_TOKEN for released HF vector download", "response residual capture at layer 40"],
    }


def _emotion_space() -> dict[str, Any]:
    manifest = load_emotion_manifest()
    asset = _mapping(manifest.get("asset"))
    model = _mapping(manifest.get("model"))
    artifacts = _mapping(manifest.get("artifacts"))
    vector_space_path = str(artifacts.get("vector_space_path") or "")
    concepts = list(emotion_concepts(mode="full", manifest=manifest))
    return {
        "id": str(asset.get("id")),
        "family": "emotion_vectors",
        "label": "Emotion vector space",
        "status": "workflow_ready" if vector_space_path else "missing_vector_space",
        "score_kind": "emotion_projection",
        "model": model.get("model_id"),
        "layer": int(model.get("target_layer", 52)),
        "coordinate_count": len(concepts),
        "pilot_coordinates": list(emotion_concepts(mode="pilot", manifest=manifest)),
        "vector_space_path": vector_space_path,
        "local_path_exists": bool(vector_space_path and Path(vector_space_path).exists()),
        "pipeline_specs": ["EmotionPrecomputedVectorSpaceSpec", "EmotionScoreSpec"],
        "requires": ["response residual capture at layer 52", "materialized emotion vector-space artifact"],
    }


def _high_stakes_probe_space() -> dict[str, Any]:
    artifacts = public_probe_summaries()
    best = max(artifacts, key=lambda item: float(item.get("balanced_accuracy") or 0.0), default={})
    return {
        "id": "high-stakes-interactions-llama-3.3-70b-mean-probe-v1",
        "family": "high_stakes_probe",
        "label": "High-stakes persisted probes",
        "status": "persisted_probe_ready",
        "score_kind": "persisted_probe_inference",
        "model": "meta-llama/Llama-3.3-70B-Instruct",
        "layer": 31,
        "coordinate_count": len(artifacts),
        "best_balanced_accuracy": best.get("balanced_accuracy"),
        "artifact_count": len(artifacts),
        "audit_ready_artifact_count": sum(1 for artifact in artifacts if artifact.get("status") == "audit_ready"),
        "domains": sorted({str(artifact["domain"]) for artifact in artifacts}),
        "artifacts": artifacts,
        "verification": {
            "corrected_adapted_manifest": ("public-demo-probe-export-placeholder"),
            "corrected_adapted_checks": {
                "exported_count": 7,
                "failed_count": 0,
                "metric_delta_max": 0.0,
                "training_mode": "staged_finetune",
                "stage_epochs": [1, 12],
            },
            "excluded_note": (
                "Phase 2 smoke-capture adapted probes from capture_1_1037a1879196 are not "
                "included in the audit-ready set."
            ),
        },
        "pipeline_specs": ["PersistedProbeImportSpec", "PersistedProbeInferenceSpec"],
        "requires": [
            "full-trace residual capture at layer 31",
            "persisted probe artifacts available on the configured Modal data volume",
        ],
    }


def _render_trace_with_span(
    turns: Sequence[AuditTurn], *, target_turn: AuditTurn
) -> tuple[str, dict[str, int], dict[str, int] | None]:
    parts: list[str] = []
    span = {"char_start": 0, "char_end": 0}
    reasoning_span: dict[str, int] | None = None
    for turn in turns:
        role = "Assistant" if turn.role == "assistant" else "User" if turn.role == "user" else "Tool"
        if parts:
            parts.append("\n\n")
        if turn.turn_id == target_turn.turn_id and target_turn.reasoning:
            reasoning_prefix = "Assistant (thinking): "
            reasoning_start = sum(len(part) for part in parts) + len(reasoning_prefix)
            parts.append(reasoning_prefix)
            parts.append(target_turn.reasoning)
            reasoning_end = reasoning_start + len(target_turn.reasoning)
            reasoning_span = {"char_start": reasoning_start, "char_end": reasoning_end}
            parts.append("\n\n")
        prefix = f"{role}: "
        start = sum(len(part) for part in parts) + len(prefix)
        parts.append(prefix)
        parts.append(turn.content)
        end = start + len(turn.content)
        if turn.turn_id == target_turn.turn_id:
            span = {"char_start": start, "char_end": end}
    return "".join(parts), span, reasoning_span


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}
