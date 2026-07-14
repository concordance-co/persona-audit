from __future__ import annotations

from backend.api import score_cache
from backend.api.db import safe_identifier
from backend.api.scores import DEFAULT_RUN_ID, HERMES_DEFAULT_RUN_ID, access, offline, sql_summaries
from backend.api.scores.provider_context import current_score_run_id


def test_score_provider_run_ids_and_identifier_validation(monkeypatch) -> None:
    monkeypatch.delenv("PERSONA_AUDIT_SCORE_RUN_ID", raising=False)

    assert current_score_run_id("tau2") == DEFAULT_RUN_ID
    assert current_score_run_id("hermes") == HERMES_DEFAULT_RUN_ID
    assert safe_identifier("valid_table_123") == "valid_table_123"

    try:
        safe_identifier("bad;drop")
    except ValueError as exc:
        assert "unsafe SQL identifier" in str(exc)
    else:
        raise AssertionError("unsafe identifier was accepted")


def test_supplemental_inventory_merge_preserves_existing_and_appends_family() -> None:
    merged = offline._merge_supplemental_inventory(
        {
            "available": True,
            "run_id": "run",
            "families": [{"score_family": "emotion", "coordinate_count": 2, "row_count": 10}],
        },
        [
            {"score_family": "assistant_axis", "coordinate": "assistant_axis_trait__calm"},
            {"score_family": "assistant_axis", "coordinate": "assistant_axis_trait__calm"},
            {"score_family": "assistant_axis", "coordinate": "assistant_axis_trait__hostile"},
        ],
    )

    assert merged["available"] is True
    assert merged["families"][0]["score_family"] == "emotion"
    supplemental = merged["families"][1]
    assert supplemental == {
        "score_family": "assistant_axis_supplemental",
        "coordinate_count": 2,
        "row_count": 3,
    }


def test_score_rows_for_coordinates_uses_supplemental_without_database(monkeypatch) -> None:
    access.score_rows_for_coordinates.cache_clear()
    monkeypatch.setattr(access, "_database_url", lambda: None)
    monkeypatch.setattr(
        access,
        "_supplemental_score_rows_for_coordinates",
        lambda coordinates, run_id: [
            {
                "score_family": "assistant_axis",
                "coordinate": coordinates[0],
                "trace_id": "trace_1",
                "turn_index": 0,
                "score": 1.0,
            }
        ],
    )

    rows = access.score_rows_for_coordinates(("assistant_axis_trait__calm",), run_id="run")

    assert rows == [
        {
            "score_family": "assistant_axis",
            "coordinate": "assistant_axis_trait__calm",
            "trace_id": "trace_1",
            "turn_index": 0,
            "score": 1.0,
        }
    ]


def test_supplemental_rows_are_not_duplicated_when_db_already_has_them() -> None:
    db_row = {
        "score_family": "assistant_axis",
        "coordinate": "assistant_axis_trait__calm",
        "trace_id": "trace_1",
        "turn_index": 0,
        "score": 1.0,
    }
    supplemental_duplicate = dict(db_row)
    supplemental_new = {
        "score_family": "assistant_axis",
        "coordinate": "assistant_axis_trait__hostile",
        "trace_id": "trace_1",
        "turn_index": 0,
        "score": 2.0,
    }

    rows = offline._append_missing_supplemental_rows([db_row], [supplemental_duplicate, supplemental_new])

    assert rows == [db_row, supplemental_new]


def test_score_summary_from_table_row_prefers_materialized_payload() -> None:
    row = {
        "run_id": "run",
        "kind": "persona_audit_score_summary",
        "version": score_cache.SCORE_SUMMARY_CACHE_VERSION,
        "score_inventory": {"available": False},
        "score_surface": {"available": False},
        "module_scores": [],
        "payload": {
            "kind": "persona_audit_score_summary",
            "version": score_cache.SCORE_SUMMARY_CACHE_VERSION,
            "run_id": "run",
            "score_inventory": {"available": True, "families": []},
            "score_surface": {"available": True},
            "module_scores": [{"trace_id": "trace_1", "module": "sycophancy", "score": 0.2}],
        },
    }

    summary = sql_summaries._score_summary_from_table_row(row, "run")

    assert summary is not None
    assert summary["score_inventory"]["available"] is True
    assert summary["module_scores"] == [{"trace_id": "trace_1", "module": "sycophancy", "score": 0.2}]


def test_score_summary_from_table_row_rejects_wrong_run_or_version() -> None:
    row = {
        "run_id": "run",
        "kind": "persona_audit_score_summary",
        "version": score_cache.SCORE_SUMMARY_CACHE_VERSION - 1,
        "score_inventory": {},
        "score_surface": {},
        "module_scores": [],
        "payload": None,
    }

    assert sql_summaries._score_summary_from_table_row(row, "run") is None
    assert (
        sql_summaries._score_summary_from_table_row(
            {**row, "version": score_cache.SCORE_SUMMARY_CACHE_VERSION}, "other"
        )
        is None
    )


def test_score_summary_cache_honors_configured_file_or_directory(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("PERSONA_AUDIT_SCORE_SUMMARY_CACHE", str(tmp_path))
    assert score_cache._score_summary_cache_path("run/id").name == "run_id.json"

    explicit_file = tmp_path / "summary.json"
    monkeypatch.setenv("PERSONA_AUDIT_SCORE_SUMMARY_CACHE", str(explicit_file))
    payload = {
        "kind": "persona_audit_score_summary",
        "version": score_cache.SCORE_SUMMARY_CACHE_VERSION,
        "run_id": "run/id",
        "score_inventory": {},
        "score_surface": {},
        "module_scores": [],
    }
    score_cache._write_score_summary_cache(payload)

    assert score_cache._score_summary_cache_path("run/id") == explicit_file
    assert score_cache._read_score_summary_cache("run/id") == payload
