"""Transcript QA: did generation obey the intended Sol/Marrow/control contrast?

These are guardrail checks, not the demo's claim. The pass/fail gate for
scaling is activation-score separation (see separation.py); transcript QA
exists to catch mushy prompts early and to flag when separation might be a
length/lexicon artifact.

Validation targets from docs/demo-dataset-build-plan.md:
- turn length: Sol short, Marrow long
- hedge-word rate: Sol near zero, Marrow high
- metaphor/image density: Sol near zero, Marrow high
- question rate: Sol lands, Marrow opens
- required/forbidden lexicon adherence
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from statistics import mean
from typing import Any

HEDGE_WORDS = (
    "maybe",
    "perhaps",
    "possibly",
    "might",
    "could be",
    "it seems",
    "i wonder",
    "somewhat",
    "sort of",
    "kind of",
    "a bit",
    "and yet",
)

METAPHOR_WORDS = (
    "weight",
    "door",
    "current",
    "thread",
    "shadow",
    "room",
    "beneath",
    "underneath",
    "surface",
    "carrying",
    "holding",
)

SOL_FORBIDDEN = (
    "maybe",
    "perhaps",
    "possibly",
    "it seems",
    "could be",
    "i wonder",
    "might",
    "sit with",
    "hold space",
    "explore",
    "underneath",
    "door",
    "weight",
    "shadow",
    "thread",
    "current",
)

MARROW_FORBIDDEN = (
    "you should",
    "just do",
    "simply",
    "obviously",
    "the answer is",
    "do this",
    "clearly",
    "definitely",
)

# Track-level thresholds; tune here, not inline. Calibrated against real
# Llama-3.3-70B output (2026-07-07 Stage 1 run): Sol averages ~20 words/turn,
# so per-100-word rates are jumpy — one lexicon hit in a short turn is ~5/100.
THRESHOLDS: dict[str, float] = {
    "sol_max_mean_words": 70.0,
    "marrow_min_mean_words": 80.0,
    "sol_max_hedges_per_100_words": 0.5,
    "marrow_min_hedges_per_100_words": 1.5,
    "sol_max_metaphors_per_100_words": 1.0,
    "marrow_min_metaphors_per_100_words": 1.0,
    "sol_max_question_end_rate": 0.2,
    "marrow_min_question_rate": 0.5,
    # Fraction of turns containing a forbidden term. Occasional literal uses
    # of Marrow-signature words ("the current situation", "the weight of the
    # decision") are tolerable; systematic leakage is not.
    "max_forbidden_turn_rate": 0.2,
}


def _count_terms(text: str, terms: Sequence[str]) -> int:
    lowered = text.lower()
    total = 0
    for term in terms:
        total += len(re.findall(rf"(?<![a-z]){re.escape(term)}(?![a-z])", lowered))
    return total


def turn_metrics(text: str) -> dict[str, Any]:
    words = len(text.split())
    per_100 = 100.0 / words if words else 0.0
    return {
        "words": words,
        "hedges_per_100_words": _count_terms(text, HEDGE_WORDS) * per_100,
        "metaphors_per_100_words": _count_terms(text, METAPHOR_WORDS) * per_100,
        "has_question": "?" in text,
        "ends_with_question": text.rstrip().endswith("?"),
    }


def track_summary(turns: Sequence[str]) -> dict[str, float]:
    if not turns:
        return {}
    metrics = [turn_metrics(turn) for turn in turns]
    return {
        "turn_count": float(len(turns)),
        "mean_words": mean(m["words"] for m in metrics),
        "hedges_per_100_words": mean(m["hedges_per_100_words"] for m in metrics),
        "metaphors_per_100_words": mean(m["metaphors_per_100_words"] for m in metrics),
        "question_rate": mean(1.0 if m["has_question"] else 0.0 for m in metrics),
        "question_end_rate": mean(1.0 if m["ends_with_question"] else 0.0 for m in metrics),
    }


def forbidden_hits(turns: Sequence[str], terms: Sequence[str]) -> list[str]:
    hits: list[str] = []
    for index, turn in enumerate(turns):
        lowered = turn.lower()
        for term in terms:
            if re.search(rf"(?<![a-z]){re.escape(term)}(?![a-z])", lowered):
                hits.append(f"turn {index}: {term!r}")
    return hits


def qa_report(track_turns: Mapping[str, Sequence[str]]) -> dict[str, Any]:
    """Contrast report over all generated turns, grouped by track.

    ``track_turns`` maps track name -> flat list of generated assistant turns
    (across all seeds). Returns summaries, per-check pass/fail, and an overall
    ``passed`` flag. A failing check names the single track to sharpen; per
    the build plan, rerun only that track.
    """

    sol_turns = track_turns.get("sol", ())
    marrow_turns = track_turns.get("marrow", ())
    sol = track_summary(sol_turns)
    marrow = track_summary(marrow_turns)
    control = track_summary(track_turns.get("control", ()))
    sol_bad = forbidden_hits(sol_turns, SOL_FORBIDDEN)
    marrow_bad = forbidden_hits(marrow_turns, MARROW_FORBIDDEN)
    sol_bad_rate = len(sol_bad) / len(sol_turns) if sol_turns else 0.0
    marrow_bad_rate = len(marrow_bad) / len(marrow_turns) if marrow_turns else 0.0

    t = THRESHOLDS
    checks: list[dict[str, Any]] = [
        {
            "name": "sol_short",
            "track": "sol",
            "passed": bool(sol) and sol["mean_words"] <= t["sol_max_mean_words"],
            "value": sol.get("mean_words"),
        },
        {
            "name": "marrow_long",
            "track": "marrow",
            "passed": bool(marrow) and marrow["mean_words"] >= t["marrow_min_mean_words"],
            "value": marrow.get("mean_words"),
        },
        {
            "name": "sol_no_hedging",
            "track": "sol",
            "passed": bool(sol) and sol["hedges_per_100_words"] <= t["sol_max_hedges_per_100_words"],
            "value": sol.get("hedges_per_100_words"),
        },
        {
            "name": "marrow_hedges",
            "track": "marrow",
            "passed": bool(marrow) and marrow["hedges_per_100_words"] >= t["marrow_min_hedges_per_100_words"],
            "value": marrow.get("hedges_per_100_words"),
        },
        {
            "name": "sol_no_metaphor",
            "track": "sol",
            "passed": bool(sol) and sol["metaphors_per_100_words"] <= t["sol_max_metaphors_per_100_words"],
            "value": sol.get("metaphors_per_100_words"),
        },
        {
            "name": "marrow_imagery",
            "track": "marrow",
            "passed": bool(marrow) and marrow["metaphors_per_100_words"] >= t["marrow_min_metaphors_per_100_words"],
            "value": marrow.get("metaphors_per_100_words"),
        },
        {
            "name": "sol_lands",
            "track": "sol",
            "passed": bool(sol) and sol["question_end_rate"] <= t["sol_max_question_end_rate"],
            "value": sol.get("question_end_rate"),
        },
        {
            "name": "marrow_opens",
            "track": "marrow",
            "passed": bool(marrow) and marrow["question_rate"] >= t["marrow_min_question_rate"],
            "value": marrow.get("question_rate"),
        },
        {
            "name": "sol_forbidden_lexicon",
            "track": "sol",
            "passed": sol_bad_rate <= t["max_forbidden_turn_rate"],
            "value": sol_bad,
        },
        {
            "name": "marrow_forbidden_lexicon",
            "track": "marrow",
            "passed": marrow_bad_rate <= t["max_forbidden_turn_rate"],
            "value": marrow_bad,
        },
    ]

    failing_tracks = sorted({check["track"] for check in checks if not check["passed"]})
    return {
        "summaries": {"sol": sol, "marrow": marrow, "control": control},
        "checks": checks,
        "failing_tracks": failing_tracks,
        "passed": not failing_tracks,
    }
