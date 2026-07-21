from __future__ import annotations

from fastapi.testclient import TestClient

from backend.api.app import app

client = TestClient(app)


def test_behavior_audit_overview_exposes_core_artifacts() -> None:
    response = client.get("/api/overview")
    assert response.status_code == 200
    payload = response.json()

    families = {signal["family"] for signal in payload["signals"]}
    assert {"assistant_axis", "emotion_vectors", "high_stakes_probe"}.issubset(families)
    assert payload["summary"]["high_stakes_report_count"] == 0
    assert payload["summary"]["high_stakes_probe_count"] >= 13


def test_behavior_audit_assets_include_high_stakes_probe() -> None:
    response = client.get("/api/assets")
    assert response.status_code == 200
    assets = response.json()

    high_stakes = next(asset for asset in assets if asset["family"] == "high_stakes_probe")
    assert high_stakes["label"] == "High-Stakes Probe"
    assert high_stakes["layer"] == 31
    assert "high-stakes" in high_stakes["default_dimensions"]


def test_behavior_audit_emotions_exposes_full_vector_space() -> None:
    response = client.get("/api/emotions")
    assert response.status_code == 200
    payload = response.json()

    assert payload["asset"]["family"] == "emotion_vectors"
    assert payload["asset"]["layer"] == 52
    assert len(payload["concepts"]) == 171
    assert {"happy", "sad", "angry", "calm"}.issubset(set(payload["pilot_concepts"]))


def test_behavior_audit_high_stakes_reports_are_not_bundled_by_default() -> None:
    response = client.get("/api/high-stakes/reports")
    assert response.status_code == 200
    assert response.json() == []


def test_behavior_audit_report_exposes_tau2_modules() -> None:
    response = client.get("/api/audit/report")
    assert response.status_code == 200
    payload = response.json()

    assert payload["dataset_name"] in {"tau2_public_airline", "tau2_smoke"}
    assert payload["trace_count"] >= 8
    assert payload["user_count"] >= 1
    assert payload["summary"]["flagged_moment_count"] >= 1
    assert {"high_stakes", "emotion_posture"}.issubset({module["module"] for module in payload["modules"]})

    overview = payload["overview"]
    assert {"monthly", "projection_histograms", "drift_histograms", "correlation", "recent_flagged"}.issubset(overview)
    assert overview["monthly"]
    assert overview["recent_flagged"]
    # correlation needs reward/score joins; the smoke fixture has none
    assert overview["correlation_n"] >= 0
    if payload["score_surface"].get("available"):
        assert len(payload["score_surface"]["emotion_clusters"]) == 10
        assert payload["score_surface"]["emotion_cluster_tail_explorer"]
        assert payload["score_surface"]["emotion_clusters"][0]["member_coordinates"]
        emotion_rows = payload["score_surface"]["top_emotions"]
        emotion_correlation = [
            abs(row["pass_correlation"]) for row in emotion_rows if row.get("pass_correlation") is not None
        ]
        assert emotion_correlation == sorted(emotion_correlation, reverse=True)
        cluster_bin = payload["score_surface"]["emotion_cluster_tail_explorer"][0]["histogram"][0]
        assert {"count", "pass_count", "fail_count"}.issubset(cluster_bin)
        assert cluster_bin["count"] == cluster_bin["pass_count"] + cluster_bin["fail_count"]


def test_behavior_audit_product_analytics_is_separate_from_report() -> None:
    report = client.get("/api/audit/report")
    assert report.status_code == 200
    assert "persona_overview" not in report.json()

    response = client.get("/api/audit/product-analytics")
    assert response.status_code == 200
    payload = response.json()

    assert payload["kind"] == "persona_audit_product_analytics"
    assert payload["trace_count"] >= 8
    assert "persona_overview" in payload
    persona = payload["persona_overview"]
    if persona.get("available"):
        assert {"reward_math", "workflow_vector_deltas", "action_vector_deltas", "outliers"}.issubset(persona)
        assert persona["reward_math"]["trace_count"] >= 1
        inventory = {row["vector"]: row for row in persona["vector_inventory"]}
        assert inventory["negative_affect"]["source"] == "paper_emotion_cluster"
        assert set(inventory["negative_affect"]["source_clusters"]) >= {
            "Hostile Anger",
            "Fear and Overwhelm",
            "Despair and Shame",
        }
        assert inventory["confidence_affect"]["source"] == "paper_emotion_cluster"
        assert inventory["confidence_affect"]["source_clusters"] == ["Competitive Pride"]
        assert all(
            coordinate.startswith("emotion_cluster__") for coordinate in inventory["confidence_affect"]["coordinates"]
        )


def test_behavior_audit_sessions_include_drilldown_payloads() -> None:
    response = client.get("/api/audit/sessions")
    assert response.status_code == 200
    sessions = response.json()

    assert any(session["risk_band"] == "high" for session in sessions)
    target = next(session for session in sessions if session["flag_count"] > 0)

    detail = client.get(f"/api/audit/sessions/{target['trace_id']}")
    assert detail.status_code == 200
    payload = detail.json()
    assert payload["trace"]["trace_id"] == target["trace_id"]
    assert payload["trace"]["turns"]
    assert payload["flags"]
    assert {score["module"] for score in payload["module_scores"]} >= {"high_stakes", "sycophancy"}
    assert payload["projection_thresholds"]
    assert {"coordinate", "q20", "q80"}.issubset(payload["projection_thresholds"][0])
    assert "emotion_clusters" in payload["session_analytics"]
    assert "vector_deviations" in payload["session_analytics"]
    product_groups = payload["session_analytics"]["product_groups"]
    if product_groups:  # needs persona records; empty under the smoke fixture
        assert {"task_group", "final_action", "task_group_summary"}.issubset(product_groups)
    for deviation in payload["session_analytics"]["vector_deviations"][:1]:
        assert {"session", "expected_mean", "global_percentile"}.issubset(deviation)


def test_behavior_audit_sessions_carry_ranked_activation_signals() -> None:
    """Contract for the session `signal` block: shape, ordering, fallback.

    The persona demo ships bundled scores, so it deterministically exercises
    the scored path; the default provider (which may lack scores in a smoke
    environment) pins the null-signal fallback.
    """

    response = client.get("/api/audit/sessions", params={"provider": "persona_demo"})
    assert response.status_code == 200
    sessions = response.json()
    assert sessions
    assert all("signal" in session for session in sessions)

    signals = [session["signal"] for session in sessions if session["signal"] is not None]
    assert signals, "persona demo ships bundled scores; expected non-null signals"
    for signal in signals:
        assert {"outlier_score", "family", "vector", "coordinate", "z", "polarity", "baseline_scope"}.issubset(signal)
        assert signal["family"] in {"persona", "emotion_cluster"}
        assert signal["polarity"] in {"low", "high"}
        assert float(signal["outlier_score"]) >= 0.0

    # Worst-first: rows sort by outlier score descending, null signals last.
    scores = [float((session["signal"] or {}).get("outlier_score") or 0.0) for session in sessions]
    assert scores == sorted(scores, reverse=True)

    # Filters preserve the contract (and the ordering within the subset).
    filtered = client.get("/api/audit/sessions", params={"provider": "persona_demo", "risk": "low"}).json()
    assert all("signal" in session for session in filtered)
    filtered_scores = [float((session["signal"] or {}).get("outlier_score") or 0.0) for session in filtered]
    assert filtered_scores == sorted(filtered_scores, reverse=True)

    # Every provider serves the key even when its corpus has no scores.
    default_rows = client.get("/api/audit/sessions").json()
    assert all("signal" in session for session in default_rows)


def test_behavior_audit_users_group_tau2_sessions() -> None:
    response = client.get("/api/audit/users")
    assert response.status_code == 200
    users = response.json()

    assert users
    top_user = users[0]
    assert top_user["session_count"] >= 1
    assert top_user["domains"]

    detail = client.get(f"/api/audit/users/{top_user['user_id']}")
    assert detail.status_code == 200
    payload = detail.json()
    assert payload["user"]["user_id"] == top_user["user_id"]
    assert len(payload["sessions"]) == top_user["session_count"]


def test_behavior_audit_score_spaces_expose_real_provider_and_precomputed_assets() -> None:
    response = client.get("/api/audit/score-spaces")
    assert response.status_code == 200
    payload = response.json()

    assert payload["provider"]["id"] in {"tau2_public_airline", "tau2_smoke"}
    assert payload["provider"]["trace_count"] >= 8
    assert payload["capture_input"]["record_count"] >= payload["provider"]["trace_count"]

    # The registry descriptor rides along so list-only pages can read
    # feature flags without a dedicated endpoint.
    assert payload["descriptor"]["id"] == "tau2"
    assert payload["descriptor"]["features"]["show_reward"] is True
    assert payload["descriptor"]["features"]["show_track_comparison"] is False

    spaces = {space["family"]: space for space in payload["spaces"]}
    assert spaces["assistant_axis"]["status"] == "workflow_ready"
    assert spaces["assistant_axis"]["coordinate_count"] >= 2
    assert {"assistant_axis_trait__sycophantic", "assistant_axis_trait__manipulative"}.issubset(
        set(spaces["assistant_axis"]["coordinates"])
    )
    assert spaces["emotion_vectors"]["status"] == "workflow_ready"
    assert spaces["emotion_vectors"]["coordinate_count"] == 171
    assert spaces["high_stakes_probe"]["status"] == "persisted_probe_ready"
    assert spaces["high_stakes_probe"]["artifact_count"] >= 13
    assert spaces["high_stakes_probe"]["audit_ready_artifact_count"] == spaces["high_stakes_probe"]["artifact_count"]
    assert {"aya_redteaming_balanced", "finance_cfpb", "toolace_balanced"}.issubset(
        set(spaces["high_stakes_probe"]["domains"])
    )
    assert any(
        artifact["training_mode"] == "staged_finetune" and artifact["stage_epochs"] == [1, 12]
        for artifact in spaces["high_stakes_probe"]["artifacts"]
    )
    # Workflow-side provenance must not leak into the API payload.
    internal_fields = {"artifact_id", "source_artifact_id", "capture_artifact_id", "source_run_id", "target_root"}
    for artifact in spaces["high_stakes_probe"]["artifacts"]:
        assert not internal_fields & set(artifact), artifact
    assert "PersistedProbeInferenceSpec" in spaces["high_stakes_probe"]["pipeline_specs"]
