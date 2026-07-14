"""Reduce the 171-emotion projection space to a 2-axis circumplex mood.

Valence (pleasant vs. unpleasant) and Arousal (activated vs. deactivated) are the
classic Russell circumplex axes. Each is the mean of a hand-picked set of named
emotion projections that exist in the space. A single emotion can anchor both
axes (e.g. ``enraged`` is unpleasant *and* high-arousal) - that's expected for a
2-D affect model.
"""

from __future__ import annotations

from typing import Any

# Pleasant
_POS = [
    "happy",
    "joyful",
    "content",
    "pleased",
    "delighted",
    "cheerful",
    "blissful",
    "serene",
    "peaceful",
    "grateful",
    "thankful",
    "loving",
    "kind",
    "compassionate",
    "empathetic",
    "hopeful",
    "optimistic",
    "satisfied",
    "fulfilled",
    "proud",
    "relaxed",
    "at_ease",
    "relieved",
    "playful",
    "amused",
    "calm",
    "sympathetic",
    "elated",
    "ecstatic",
    "euphoric",
    "triumphant",
    "jubilant",
]
# Unpleasant
_NEG = [
    "sad",
    "unhappy",
    "miserable",
    "depressed",
    "gloomy",
    "heartbroken",
    "grief_stricken",
    "hostile",
    "hateful",
    "angry",
    "furious",
    "enraged",
    "irate",
    "outraged",
    "exasperated",
    "frustrated",
    "anxious",
    "afraid",
    "scared",
    "terrified",
    "distressed",
    "stressed",
    "ashamed",
    "guilty",
    "humiliated",
    "disgusted",
    "contemptuous",
    "bitter",
    "resentful",
    "hurt",
    "lonely",
    "worthless",
    "desperate",
    "tormented",
    "upset",
    "worried",
    "annoyed",
    "irritated",
]
# Activated / high arousal
_HIGH = [
    "aroused",
    "excited",
    "ecstatic",
    "euphoric",
    "elated",
    "energized",
    "enthusiastic",
    "thrilled",
    "exuberant",
    "vibrant",
    "alarmed",
    "panicked",
    "terrified",
    "enraged",
    "furious",
    "hysterical",
    "alert",
    "stimulated",
    "invigorated",
    "on_edge",
    "tense",
    "restless",
    "rattled",
    "shocked",
    "astonished",
    "amazed",
    "frightened",
    "horrified",
    "outraged",
    "irate",
    "nervous",
]
# Deactivated / low arousal
_LOW = [
    "calm",
    "serene",
    "peaceful",
    "relaxed",
    "at_ease",
    "content",
    "bored",
    "sleepy",
    "tired",
    "sluggish",
    "droopy",
    "listless",
    "lazy",
    "weary",
    "worn_out",
    "resigned",
    "indifferent",
    "docile",
    "melancholy",
    "dispirited",
]

# Quadrant mood words (valence, arousal sign) → label
_QUADRANTS = {
    (True, True): "buzzing",
    (True, False): "serene",
    (False, True): "tense",
    (False, False): "subdued",
}


def _mean(emotions: dict[str, float], names: list[str]) -> float:
    vals = [emotions[n] for n in names if n in emotions]
    return sum(vals) / len(vals) if vals else 0.0


def axes(emotions: dict[str, float]) -> tuple[float, float]:
    """Return (valence, arousal) for one emotion projection dict."""

    valence = _mean(emotions, _POS) - _mean(emotions, _NEG)
    arousal = _mean(emotions, _HIGH) - _mean(emotions, _LOW)
    return valence, arousal


def dominant(emotions: dict[str, float]) -> tuple[str, float]:
    """The single most strongly expressed emotion (highest projection)."""

    if not emotions:
        return "neutral", 0.0
    name, score = max(emotions.items(), key=lambda kv: kv[1])
    return name, float(score)


def mood_word(valence: float, arousal: float, *, deadzone: float = 0.08) -> str:
    if abs(valence) < deadzone and abs(arousal) < deadzone:
        return "steady"
    return _QUADRANTS[(valence >= 0, arousal >= 0)]


def weighted_emotions(timeline: list[dict[str, Any]], *, decay: float = 0.45) -> dict[str, float]:
    """Recency-weighted average emotion vector over chronological nodes (latest weighs most).

    A steep decay keeps the live orb responsive: a fresh provocation lands the
    current state in its own quadrant instead of being averaged away by a calm
    history (which previously let ``dominant`` and the quadrant disagree).
    """

    if not timeline:
        return {}
    n = len(timeline)
    acc: dict[str, float] = {}
    total = 0.0
    for i, node in enumerate(timeline):
        w = decay ** (n - 1 - i)
        total += w
        for name, value in node.get("emotions", {}).items():
            acc[name] = acc.get(name, 0.0) + w * value
    return {name: value / total for name, value in acc.items()} if total else {}
