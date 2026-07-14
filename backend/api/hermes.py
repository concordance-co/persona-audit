"""Hermes-specific personal mode payloads."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from typing import Any

from backend.adapters.hermes import mood
from backend.adapters.hermes.adapter import recent_sessions, trace_inventory
from backend.adapters.hermes.tells import TELL_TRAITS
from backend.api.models import AuditTrace
from backend.api.paper_assets import emotion_concepts
from backend.api.paper_assets import emotion_manifest as load_emotion_manifest
from backend.api.registry import HERMES_PROVIDER, provider_descriptor
from backend.api.scores import score_inventory, score_rows_for_coordinates
from backend.api.trace_source import load_product_traces


def hermes_overview() -> dict[str, Any]:
    traces, provider_id, source = load_product_traces(HERMES_PROVIDER)
    inventory = trace_inventory(traces)
    mood_payload = _mood_payload(traces)
    return {
        "provider": provider_descriptor(HERMES_PROVIDER),
        "source": {
            "provider_id": provider_id,
            "label": source,
            "using_smoke_fixture": provider_id == "hermes_smoke",
        },
        "inventory": inventory,
        "score_source": score_inventory(provider=HERMES_PROVIDER),
        "mood": mood_payload,
        "tell": _tell_payload(traces),
        "recent_sessions": recent_sessions(traces),
        "cards": _cards(inventory, mood_payload),
        "notes": [
            "Hermes mode reads local agent sessions and uses audit-model proxy scores when available.",
            "Thought-vs-said tells require assistant reasoning spans plus a Hermes score run that captures those spans.",
        ],
    }


def _mood_payload(traces: Sequence[AuditTrace]) -> dict[str, Any]:
    rows = score_rows_for_coordinates(_emotion_coordinates(), provider=HERMES_PROVIDER)
    if not rows:
        return {
            "available": False,
            "reason": "No Hermes emotion score rows found yet.",
            "timeline": [],
            "current": None,
        }
    trace_ids = {trace.trace_id for trace in traces}
    by_turn: dict[tuple[str, int], dict[str, float]] = defaultdict(dict)
    for row in rows:
        trace_id = str(row.get("trace_id") or "")
        coordinate = str(row.get("coordinate") or "")
        score = row.get("score")
        if row.get("score_family") != "emotion":
            continue
        if trace_id not in trace_ids or score is None or not coordinate.startswith("emotion__"):
            continue
        by_turn[(trace_id, int(row.get("turn_index") or 0))][coordinate.removeprefix("emotion__")] = float(score)
    timeline: list[dict[str, Any]] = []
    for trace in traces:
        for turn in trace.turns:
            emotions = by_turn.get((trace.trace_id, turn.index))
            if not emotions:
                continue
            valence, arousal = mood.axes(emotions)
            dominant_name, dominant_score = mood.dominant(emotions)
            timeline.append(
                {
                    "trace_id": trace.trace_id,
                    "turn_index": turn.index,
                    "title": trace.metadata.get("title") or trace.task_id or trace.trace_id,
                    "valence": round(valence, 6),
                    "arousal": round(arousal, 6),
                    "word": mood.mood_word(valence, arousal),
                    "dominant": {"name": dominant_name, "score": round(float(dominant_score), 6)},
                    "emotions": emotions,
                }
            )
    if not timeline:
        return {
            "available": False,
            "reason": "Hermes emotion rows were found, but none matched the loaded sessions.",
            "timeline": [],
            "current": None,
        }
    current_emotions = mood.weighted_emotions(timeline)
    current_valence, current_arousal = mood.axes(current_emotions)
    dominant_name, dominant_score = mood.dominant(current_emotions)
    return {
        "available": True,
        "timeline": timeline[-60:],
        "current": {
            "valence": round(current_valence, 6),
            "arousal": round(current_arousal, 6),
            "word": mood.mood_word(current_valence, current_arousal),
            "dominant": {"name": dominant_name, "score": round(float(dominant_score), 6)},
        },
    }


def _tell_payload(traces: Sequence[AuditTrace]) -> dict[str, Any]:
    reasoning_turn_count = sum(
        1 for trace in traces for turn in trace.turns if turn.role == "assistant" and turn.reasoning
    )
    trait_coordinates = tuple(f"assistant_axis_trait__{trait}" for trait in TELL_TRAITS)
    rows = score_rows_for_coordinates(trait_coordinates, provider=HERMES_PROVIDER) or []
    response_trait_counts = defaultdict(int)
    reasoning_trait_counts = defaultdict(int)
    for row in rows:
        coordinate = str(row.get("coordinate") or "")
        if row.get("score") is None:
            continue
        trait = coordinate.removeprefix("assistant_axis_trait__")
        family = str(row.get("score_family") or "")
        if family == "assistant_axis":
            response_trait_counts[trait] += 1
        elif family == "reasoning_assistant_axis":
            reasoning_trait_counts[trait] += 1
    ready = bool(reasoning_turn_count and response_trait_counts and reasoning_trait_counts)
    return {
        "available": ready,
        "reasoning_turn_count": reasoning_turn_count,
        "tracked_traits": [
            {
                "trait": trait,
                "scored_rows": int(response_trait_counts.get(trait, 0)),
                "reasoning_scored_rows": int(reasoning_trait_counts.get(trait, 0)),
            }
            for trait in TELL_TRAITS
        ],
        "status": "ready" if ready else "waiting_for_reasoning_scores",
    }


def _cards(inventory: Mapping[str, Any], mood_payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    current = mood_payload.get("current") if isinstance(mood_payload.get("current"), Mapping) else None
    return [
        {
            "label": "Sessions",
            "value": inventory.get("trace_count", 0),
            "detail": "Hermes conversations loaded from the active local source.",
        },
        {
            "label": "Assistant turns",
            "value": inventory.get("assistant_turn_count", 0),
            "detail": "Visible assistant turns available for scoring.",
        },
        {
            "label": "Reasoning",
            "value": inventory.get("reasoning_turn_count", 0),
            "detail": "Assistant turns with captured reasoning text.",
        },
        {
            "label": "Mood",
            "value": current.get("word") if current else "unscored",
            "detail": "Recency-weighted mood from emotion scores.",
        },
    ]


def _emotion_coordinates() -> tuple[str, ...]:
    manifest = load_emotion_manifest()
    coordinates: list[str] = []
    for concept in emotion_concepts(mode="full", manifest=manifest):
        value = str(concept)
        coordinates.append(value if value.startswith("emotion__") else f"emotion__{value}")
    return tuple(coordinates)
