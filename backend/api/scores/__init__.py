"""Score access for Persona Audit: activation scores from Postgres or bundled JSON.

Module map:
- access.py           public entry points (score_summary, score_rows_for_*, real_*)
- provider_context.py provider ContextVar + run-id/table resolution
- sql_summaries.py    Postgres summary builders (SQL twin of offline.py)
- offline.py          bundled supplemental-JSON path (offline twin of sql_summaries.py)
- emotion_clusters.py cluster metadata from the papers.voice emotion asset
- shaping.py          row -> view-model helpers shared by both paths
"""

from backend.api.providers import hermes as _hermes_provider
from backend.api.providers import tau2 as _tau2_provider
from backend.api.scores.access import (
    real_module_scores,
    real_score_details,
    real_score_summary,
    score_inventory,
    score_rows_for_coordinates,
    score_rows_for_trace,
    score_summary,
    score_surface,
)
from backend.api.scores.emotion_clusters import (
    EMOTION_CLUSTER_SCORE_FAMILY,
    NEGATIVE_AFFECT_COORDINATES,
    SELECTED_SESSION_EMOTIONS,
    emotion_cluster_metadata,
    emotion_cluster_metadata_by_coordinate,
)

# Historical run ids for the shipped fixtures live on the provider specs.
DEFAULT_RUN_ID = _tau2_provider.DEFAULT_RUN_ID
HERMES_DEFAULT_RUN_ID = _hermes_provider.DEFAULT_RUN_ID

__all__ = [
    "DEFAULT_RUN_ID",
    "HERMES_DEFAULT_RUN_ID",
    "EMOTION_CLUSTER_SCORE_FAMILY",
    "NEGATIVE_AFFECT_COORDINATES",
    "SELECTED_SESSION_EMOTIONS",
    "emotion_cluster_metadata",
    "emotion_cluster_metadata_by_coordinate",
    "real_module_scores",
    "real_score_details",
    "real_score_summary",
    "score_inventory",
    "score_rows_for_coordinates",
    "score_rows_for_trace",
    "score_summary",
    "score_surface",
]
