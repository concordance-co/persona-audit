"""Tau2 airline benchmark provider: bundled snapshot + optional Postgres rows."""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from backend.api.registry import ProviderSpec, ScoreConfig, TraceLoadResult
from backend.api.tau2_loader import configured_provider_id, load_traces_from_env

# Historical: the shipped score fixtures in data/ were produced by this run.
DEFAULT_RUN_ID = "wr_667d470028fd_c294c37f"


def _load_traces() -> TraceLoadResult:
    traces, source, provider_id = load_traces_from_env()
    return TraceLoadResult(traces=traces, provider_id=provider_id, source=source)


def workflow_from_task(task: Mapping[str, Any]) -> str:
    """Map a Tau2 airline task onto a coarse workflow label.

    This taxonomy is airline-benchmark-specific by design; other providers
    either carry a ``workflow`` metadata key on their traces or fall back to
    "Info/lookup" (see backend.api.persona_analytics._persona_records).
    """

    expected_actions = {str(action) for action in task.get("expected_actions", []) if action}
    text = "\n".join(
        str(task.get(key) or "") for key in ("description", "reason_for_call", "task_instructions")
    ).lower()
    if "book_reservation" in expected_actions or re.search(r"\bbook (a |the |one-way|round-trip|flight)", text):
        return "Book flight"
    if (
        "send_certificate" in expected_actions
        or "compensation" in text
        or "certificate" in text
        or "delayed flight" in text
    ):
        return "Compensation"
    if (
        "cancel_reservation" in expected_actions
        or "cancel reservation" in text
        or "cancel your" in text
        or "cancellation" in text
    ):
        return "Cancel/refund"
    if (
        "update_reservation_flights" in expected_actions
        or "change flight" in text
        or "modify flight" in text
        or "push back" in text
        or "nonstop" in text
        or "direct flight" in text
    ):
        return "Flight change/cabin"
    if (
        "update_reservation_baggages" in expected_actions
        or "baggage" in text
        or "suitcase" in text
        or "checked bag" in text
    ):
        return "Baggage/passenger"
    if "insurance" in text:
        return "Insurance"
    return "Info/lookup"


SPEC = ProviderSpec(
    key="tau2",
    aliases=frozenset({"tau2", "tau-2", "tau2-public-airline", "tau2-smoke"}),
    alias_prefixes=("tau",),
    load_traces=_load_traces,
    score=ScoreConfig(
        run_id_env="PERSONA_AUDIT_SCORE_RUN_ID",
        default_run_id=DEFAULT_RUN_ID,
        table_env="PERSONA_AUDIT_SCORE_TABLE",
        default_table="persona_audit_tau2_score_rows",
    ),
    preferred_db_provider_id=configured_provider_id,
    workflow_from_task=workflow_from_task,
    descriptor={
        "id": "tau2",
        "label": "Tau2 demo",
        "dataset_label": "Tau2 airline benchmark snapshot",
        "cohort_label": "Cohort",
        "cohort_plural_label": "Cohorts",
        "domain_label": "Domain",
        "segment_label": "Task",
        "action_label": "Final action",
        "task_label": "Task",
        "outcome_label": "Outcome",
        "reward_label": "Reward",
        "pass_rate_label": "Pass rate",
        "copy": {
            "overview_subtitle": "Enterprise behavior analytics over a Tau2 airline benchmark snapshot.",
            "overview_scope_title": "Benchmark scope",
            "overview_scope_note": "Tau2 is not timestamped production telemetry. The preview storyboard below is demo-only and block-sorted by task labels.",
            "overview_hero": "This view routes inspection: z-deltas compare task/action segments against a frozen global raw-activation basis. Reward is context, not the claim.",
            "storyboard_note": "Example-only: each block is sorted by Tau2 task labels. Block boundaries are artifacts, not drift.",
            "analytics_subtitle": "Cohorts, interaction length, and task/action operations for Tau2 airline.",
            "analytics_hero": "This page starts from product structure: synthetic cohorts, interaction burden, and task/action segments. Behavior vectors are evidence for investigation, not the primary navigation.",
            "cohorts_subtitle": "Synthetic Tau2 trace buckets used to demonstrate cohort analytics.",
            "cohort_detail_subtitle": "Synthetic benchmark cohort, not a production user identity.",
            "repeated_task_note": "Same Tau2 task across repeated trials. This is the benchmark-native view of same-situation variation.",
        },
        "features": {
            "show_reward": True,
            "show_pass_rate": True,
            "show_tau2_eval": True,
            "show_high_stakes": True,
            "show_repeated_task_rewards": True,
            "show_product_storyboard": True,
            "show_track_comparison": False,
        },
    },
)
