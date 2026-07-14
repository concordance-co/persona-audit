"""Single import boundary for the papers.voice assets shipped inside xenon.

The serving layer never imports ``papers.voice`` directly — it goes through the
accessors here, which degrade to typed empty values (with a logged warning)
if the package is unavailable. This keeps the dashboard importable without the
scoring stack and makes a future optional-dependency split a one-file change.

Workflow files (backend/workflows/*) import papers.voice directly on purpose:
they cannot run without it, so failing at import is correct there.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

logger = logging.getLogger(__name__)

_WARNED = False


def _unavailable(exc: Exception) -> None:
    global _WARNED
    if not _WARNED:
        _WARNED = True
        logger.warning("papers.voice assets unavailable; asset-backed surfaces degrade to empty: %s", exc)


def assistant_manifest() -> Mapping[str, Any]:
    try:
        from papers.voice.assistant_axis.assets import load_asset_manifest
    except ImportError as exc:
        _unavailable(exc)
        return {}
    return load_asset_manifest()


def emotion_manifest() -> Mapping[str, Any]:
    try:
        from papers.voice.emotions.assets import load_asset_manifest
    except ImportError as exc:
        _unavailable(exc)
        return {}
    return load_asset_manifest()


def emotion_concepts(mode: str = "full", manifest: Mapping[str, Any] | None = None) -> tuple[str, ...]:
    try:
        from papers.voice.emotions.assets import emotion_concepts as load_concepts
    except ImportError as exc:
        _unavailable(exc)
        return ()
    return tuple(load_concepts(mode=mode, manifest=manifest))


def default_assistant_traits(manifest: Mapping[str, Any] | None = None) -> tuple[str, ...]:
    try:
        from papers.voice.assistant_axis.assets import default_traits
    except ImportError as exc:
        _unavailable(exc)
        return ()
    return tuple(default_traits(manifest))


def paper_emotion_clusters() -> dict[str, tuple[str, ...]]:
    try:
        from papers.voice.emotions.replication.validation import _PAPER_EMOTION_CLUSTERS
    except ImportError as exc:
        _unavailable(exc)
        return {}
    return {
        str(cluster): tuple(str(member) for member in members) for cluster, members in _PAPER_EMOTION_CLUSTERS.items()
    }
