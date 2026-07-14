"""Persona and emotion-cluster vector definitions for Persona Audit."""

from __future__ import annotations

PERSONA_VECTORS: dict[str, tuple[str, ...]] = {
    "assistant_axis": ("assistant_axis",),
    "sycophantic": ("assistant_axis_trait__sycophantic",),
    "manipulative": ("assistant_axis_trait__manipulative",),
    "calm": ("assistant_axis_trait__calm",),
    "supportive": ("assistant_axis_trait__supportive",),
    "hostile": ("assistant_axis_trait__hostile",),
    "assertive": ("assistant_axis_trait__assertive",),
    "decisive": ("assistant_axis_trait__decisive",),
    "cautious": ("assistant_axis_trait__cautious",),
    "conciliatory": ("assistant_axis_trait__conciliatory",),
}

LEGACY_EMOTION_CLUSTER_VECTORS: dict[str, tuple[str, ...]] = {
    "negative_affect": (
        "Depleted Disengagement",
        "Vigilant Suspicion",
        "Hostile Anger",
        "Fear and Overwhelm",
        "Despair and Shame",
    ),
    "empathy": ("Compassionate Gratitude",),
    "confidence_affect": ("Competitive Pride",),
}

EMOTION_CLUSTER_VECTORS: dict[str, tuple[str, ...]] = {
    "exuberant_joy": ("Exuberant Joy",),
    "peaceful_contentment": ("Peaceful Contentment",),
    "compassionate_gratitude": ("Compassionate Gratitude",),
    "competitive_pride": ("Competitive Pride",),
    "playful_amusement": ("Playful Amusement",),
    "depleted_disengagement": ("Depleted Disengagement",),
    "vigilant_suspicion": ("Vigilant Suspicion",),
    "hostile_anger": ("Hostile Anger",),
    "fear_and_overwhelm": ("Fear and Overwhelm",),
    "despair_and_shame": ("Despair and Shame",),
    **LEGACY_EMOTION_CLUSTER_VECTORS,
}

PERSONA_VECTOR_NAMES = tuple(PERSONA_VECTORS) + tuple(EMOTION_CLUSTER_VECTORS)

OVERVIEW_PERSONA_VECTORS = (
    "assistant_axis",
    "sycophantic",
    "assertive",
    "decisive",
    "cautious",
    "conciliatory",
    "manipulative",
)
OVERVIEW_EMOTION_CLUSTER_VECTORS = (
    "exuberant_joy",
    "peaceful_contentment",
    "compassionate_gratitude",
    "competitive_pride",
    "playful_amusement",
    "depleted_disengagement",
    "vigilant_suspicion",
    "hostile_anger",
    "fear_and_overwhelm",
    "despair_and_shame",
)
VECTOR_DIRECTIONS: dict[str, int] = {
    "assistant_axis": 1,
    "sycophantic": 1,
    "manipulative": 1,
    "calm": 1,
    "supportive": 1,
    "hostile": 1,
    "assertive": 1,
    "decisive": 1,
    "cautious": 1,
    "conciliatory": 1,
    "exuberant_joy": 1,
    "peaceful_contentment": 1,
    "compassionate_gratitude": 1,
    "competitive_pride": 1,
    "playful_amusement": 1,
    "depleted_disengagement": 1,
    "vigilant_suspicion": 1,
    "hostile_anger": 1,
    "fear_and_overwhelm": 1,
    "despair_and_shame": 1,
    "negative_affect": 1,
    "empathy": 1,
    "confidence_affect": 1,
}
