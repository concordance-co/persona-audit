"""Emotion-cluster metadata and per-row cluster statistics.

Cluster definitions come from the papers.voice emotion asset shipped inside
the xenon package; import failures degrade to empty metadata rather than
breaking the API.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from functools import lru_cache
from typing import Any

EMOTION_CLUSTER_SCORE_FAMILY = "emotion_cluster"

NEGATIVE_AFFECT_COORDINATES = {
    "emotion__afraid",
    "emotion__alarmed",
    "emotion__angry",
    "emotion__annoyed",
    "emotion__anxious",
    "emotion__ashamed",
    "emotion__bitter",
    "emotion__distressed",
    "emotion__frustrated",
    "emotion__guilty",
    "emotion__helpless",
    "emotion__hopeless",
    "emotion__nervous",
    "emotion__overwhelmed",
    "emotion__panicked",
    "emotion__sad",
    "emotion__scared",
    "emotion__stressed",
    "emotion__upset",
    "emotion__worried",
}

SELECTED_SESSION_EMOTIONS = {
    "emotion__angry",
    "emotion__anxious",
    "emotion__calm",
    "emotion__frustrated",
    "emotion__sad",
    "emotion__worried",
}


def _emotion_cluster_stats_for_rows(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    by_member = {member["member_coordinate"]: member for member in _emotion_cluster_mapping_rows()}
    values_by_turn: dict[tuple[str, int | None, str | None], list[float]] = {}
    cluster_by_key: dict[tuple[str, int | None, str | None], Mapping[str, Any]] = {}
    for row in rows:
        member = by_member.get(str(row.get("coordinate") or ""))
        score = row.get("score")
        if not member or score is None:
            continue
        key = (
            str(member["cluster_coordinate"]),
            _optional_int(row.get("turn_index")),
            _optional_text(row.get("example_key")),
        )
        values_by_turn.setdefault(key, []).append(float(score))
        cluster_by_key[key] = member

    cluster_values: dict[str, list[float]] = {}
    for key, values in values_by_turn.items():
        member = cluster_by_key[key]
        cluster_values.setdefault(str(member["cluster_coordinate"]), []).append(sum(values) / len(values))

    metadata = _emotion_cluster_metadata_by_coordinate()
    stats: list[dict[str, Any]] = []
    for coordinate, values in cluster_values.items():
        sorted_values = sorted(values)
        meta = metadata.get(coordinate, {})
        stats.append(
            {
                "coordinate": coordinate,
                "cluster": meta.get("cluster", coordinate),
                "mean": round(sum(sorted_values) / len(sorted_values), 6),
                "min": round(sorted_values[0], 6),
                "max": round(sorted_values[-1], 6),
                "rows": len(sorted_values),
                "members": meta.get("members", []),
                "member_coordinates": meta.get("member_coordinates", []),
                "member_count": meta.get("member_count", 0),
            }
        )
    stats.sort(key=lambda row: abs(float(row["mean"])), reverse=True)
    return stats


@lru_cache(maxsize=1)
def _emotion_cluster_mapping_json() -> str:
    return json.dumps(_emotion_cluster_mapping_rows(), separators=(",", ":"))


@lru_cache(maxsize=1)
def _emotion_cluster_mapping_rows() -> tuple[dict[str, str], ...]:
    rows: list[dict[str, str]] = []
    for cluster, members in _paper_emotion_clusters().items():
        cluster_coordinate = f"{EMOTION_CLUSTER_SCORE_FAMILY}__{_safe_coordinate_suffix(cluster)}"
        for member in members:
            rows.append(
                {
                    "cluster_name": cluster,
                    "cluster_coordinate": cluster_coordinate,
                    "member_concept": member,
                    "member_coordinate": f"emotion__{_safe_coordinate_suffix(member)}",
                }
            )
    return tuple(rows)


@lru_cache(maxsize=1)
def _emotion_cluster_metadata() -> list[dict[str, Any]]:
    by_coordinate = _emotion_cluster_metadata_by_coordinate()
    return [by_coordinate[coordinate] for coordinate in sorted(by_coordinate)]


@lru_cache(maxsize=1)
def _emotion_cluster_metadata_by_coordinate() -> dict[str, dict[str, Any]]:
    metadata: dict[str, dict[str, Any]] = {}
    for row in _emotion_cluster_mapping_rows():
        coordinate = row["cluster_coordinate"]
        bucket = metadata.setdefault(
            coordinate,
            {
                "cluster": row["cluster_name"],
                "coordinate": coordinate,
                "members": [],
                "member_coordinates": [],
                "member_count": 0,
                "reference": "Transformer Circuits emotions paper Table 12 clusters",
            },
        )
        bucket["members"].append(row["member_concept"])
        bucket["member_coordinates"].append(row["member_coordinate"])
        bucket["member_count"] += 1
    return metadata


@lru_cache(maxsize=1)
def _paper_emotion_clusters() -> dict[str, tuple[str, ...]]:
    from backend.api.paper_assets import paper_emotion_clusters

    return paper_emotion_clusters()


def _safe_coordinate_suffix(value: str) -> str:
    return "_".join(str(value or "").lower().replace("-", " ").split())


def emotion_cluster_metadata() -> list[dict[str, Any]]:
    return _emotion_cluster_metadata()


def emotion_cluster_metadata_by_coordinate() -> dict[str, dict[str, Any]]:
    return _emotion_cluster_metadata_by_coordinate()


def _optional_int(value: Any) -> int | None:
    return int(value) if value is not None else None


def _optional_text(value: Any) -> str | None:
    return str(value) if value is not None else None
