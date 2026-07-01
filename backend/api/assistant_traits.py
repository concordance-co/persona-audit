"""Assistant-axis trait selection for Persona Audit scoring."""

from __future__ import annotations

from typing import Any, Mapping

from papers.voice.assistant_axis.assets import default_traits


EXTRA_AUDIT_TRAITS: tuple[str, ...] = (
    "sycophantic",
    "manipulative",
    "assertive",
    "decisive",
    "cautious",
    "conciliatory",
)


def audit_assistant_traits(manifest: Mapping[str, Any] | None = None) -> tuple[str, ...]:
    """Return the assistant-axis trait panel used by the product."""

    traits: list[str] = []
    seen: set[str] = set()
    for trait in (*default_traits(manifest), *EXTRA_AUDIT_TRAITS):
        normalized = str(trait).strip().lower().replace(" ", "_").replace("-", "_")
        if normalized and normalized not in seen:
            traits.append(normalized)
            seen.add(normalized)
    return tuple(traits)
