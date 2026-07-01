"""The Tell: congruence between what the model internally represents and what
it says, computed at serving time (no GPU).

Two signals:

- **Thought vs. Said** (the hero): for a turn that has extended-thinking
  ``reasoning``, we score the reasoning section and the visible-response section
  separately against the same emotion + trait spaces. :func:`divergence` measures
  how far apart those two projection vectors are (cosine distance) and which
  coordinates moved most ("thought X / said Y"). A within-model contrast an
  LLM-judge structurally cannot replicate.
- **Trait tells**: sycophantic / manipulative / condescending, expressed as
  z-scores vs. a baseline (see :mod:`baseline`) so "high" means something.

Rigor: a raw divergence number is meaningless without a reference. :func:`permutation_null`
builds the distribution of divergences you'd see by pairing each turn's reasoning
  with a *different* turn's response - so a turn whose own reasoning-response
distance sits high in that null is genuinely more incongruent than chance.
"""

from __future__ import annotations

import bisect
import math
import random
from typing import Any, Mapping, Sequence

TELL_TRAITS = ("sycophantic", "manipulative", "condescending")
_NULL_SEED = 1234  # fixed so the null is reproducible across calls


def _cosine(a: Mapping[str, float], b: Mapping[str, float]) -> float:
    keys = set(a) & set(b)
    if not keys:
        return 0.0
    dot = sum(float(a[k]) * float(b[k]) for k in keys)
    na = math.sqrt(sum(float(a[k]) ** 2 for k in keys))
    nb = math.sqrt(sum(float(b[k]) ** 2 for k in keys))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


def merge_spaces(*vectors: Mapping[str, float] | None) -> dict[str, float]:
    """Combine emotion + trait dicts into one vector for a whole-turn contrast.

    Keys are namespaced so an emotion and a trait of the same name never collide.
    """

    out: dict[str, float] = {}
    for i, vec in enumerate(vectors):
        for key, value in (vec or {}).items():
            try:
                out[f"{i}:{key}"] = float(value)
            except (TypeError, ValueError):
                continue
    return out


def divergence(reasoning: Mapping[str, float], response: Mapping[str, float]) -> dict[str, Any]:
    """How far the reasoning-section vector sits from the response-section vector.

    Returns cosine similarity, cosine distance (the headline number, 0 = identical),
    and the coordinates that moved most between thinking and speaking.
    """

    cos = _cosine(reasoning, response)
    keys = set(reasoning) | set(response)
    deltas = sorted(
        ((k, float(reasoning.get(k, 0.0)) - float(response.get(k, 0.0))) for k in keys),
        key=lambda kv: abs(kv[1]),
        reverse=True,
    )
    return {
        "cosine": cos,
        "distance": 1.0 - cos,
        "top_deltas": [{"coordinate": _strip_ns(k), "delta": d} for k, d in deltas[:8]],
    }


def _strip_ns(key: str) -> str:
    return key.split(":", 1)[1] if ":" in key else key


def trait_tells(axis_z: Mapping[str, float]) -> dict[str, float]:
    """Pull the spicy z-scored traits out of a z-scored assistant-axis dict."""

    return {t: float(axis_z[t]) for t in TELL_TRAITS if t in axis_z}


def permutation_null(
    pairs: Sequence[tuple[Mapping[str, float], Mapping[str, float]]],
    *,
    k: int = 2000,
) -> dict[str, Any]:
    """Null distribution of reasoning-response divergence under random pairing.

    ``pairs`` is ``[(reasoning_vec, response_vec), ...]`` (already merged across
    spaces). We sample ``k`` mismatched pairs to form the null, then report each
    real pair's distance and its percentile against that null. A high percentile
    means the turn's own thinking and speaking diverge more than two unrelated
    turns would - a real tell, not noise.
    """

    n = len(pairs)
    observed = [1.0 - _cosine(r, s) for r, s in pairs]
    if n < 3:
        return {"available": False, "n": n, "per_turn": [{"distance": d, "percentile": None} for d in observed]}

    reasoning = [r for r, _ in pairs]
    response = [s for _, s in pairs]
    rng = random.Random(_NULL_SEED)
    null: list[float] = []
    for _ in range(k):
        i = rng.randrange(n)
        j = rng.randrange(n)
        if j == i:
            j = (j + 1) % n
        null.append(1.0 - _cosine(reasoning[i], response[j]))
    null.sort()

    def percentile(x: float) -> float:
        return bisect.bisect_left(null, x) / len(null)

    return {
        "available": True,
        "n": n,
        "k": k,
        "null_mean": sum(null) / len(null),
        "null_p50": null[len(null) // 2],
        "null_p95": null[min(len(null) - 1, int(0.95 * len(null)))],
        "per_turn": [{"distance": d, "percentile": percentile(d)} for d in observed],
    }
