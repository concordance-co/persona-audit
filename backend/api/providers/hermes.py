"""Hermes provider: local agent sessions from a state.db, or the bundled demo."""

from __future__ import annotations

from backend.adapters.hermes.adapter import DEMO_PROVIDER_ID, active_provider_id, load_audit_traces_from_env
from backend.api.registry import ProviderSpec, ScoreConfig, TraceLoadResult

# Historical run id: names score rows uploaded before the persona_audit rename.
DEFAULT_RUN_ID = "behavior_audit_hermes_scoring_v1"
# The shipped score cache in data/supplemental_scores/ for the bundled demo.
DEMO_RUN_ID = "persona_audit_hermes_demo_v1"


def _load_traces() -> TraceLoadResult:
    traces, provider_id, source = load_audit_traces_from_env()
    return TraceLoadResult(traces=traces, provider_id=provider_id, source=source)


def _default_run_id() -> str:
    """Demo run id when the bundled demo is the active source, else historical."""

    return DEMO_RUN_ID if active_provider_id() == DEMO_PROVIDER_ID else DEFAULT_RUN_ID


SPEC = ProviderSpec(
    key="hermes",
    aliases=frozenset({"hermes", "hermes-local", "hermes-smoke", "hermes-agent"}),
    alias_prefixes=("hermes",),
    load_traces=_load_traces,
    score=ScoreConfig(
        run_id_env="PERSONA_AUDIT_HERMES_SCORE_RUN_ID",
        default_run_id=_default_run_id,
        table_env="PERSONA_AUDIT_HERMES_SCORE_TABLE",
        default_table="persona_audit_hermes_score_rows",
    ),
    db_provider_id_prefix="hermes",
    preferred_db_provider_id=lambda: "hermes_local",
    supports_reward_math=False,
    descriptor={
        "id": "hermes",
        "label": "Hermes mode",
        "dataset_label": "Local Hermes agent sessions",
        "cohort_label": "User",
        "cohort_plural_label": "Users",
        "domain_label": "Source",
        "segment_label": "Session topic",
        "action_label": "End state",
        "task_label": "Session",
        "outcome_label": "End reason",
        "reward_label": "Activation",
        "pass_rate_label": "Signal rate",
        "copy": {
            "overview_subtitle": "Personal behavior analytics over local Hermes sessions.",
            "overview_scope_title": "Hermes scope",
            "overview_scope_note": "Hermes reads local agent sessions. Scores are proxy activations from the audit model, not the agent's own hidden state.",
            "overview_hero": "This view shows how your local assistant sounds across sessions: trait baselines, emotion posture, and sessions worth inspecting.",
            "storyboard_note": "Example-only: Hermes sessions are ordered by local metadata, not benchmark blocks.",
            "analytics_subtitle": "Users, session length, and source/topic patterns for Hermes.",
            "analytics_hero": "Hermes mode starts from local agent use: session source, topic, interaction length, and optional reasoning coverage.",
            "cohorts_subtitle": "Hermes users found in the local session store.",
            "cohort_detail_subtitle": "Local Hermes user/session cohort.",
            "repeated_task_note": "Sessions with similar local topic labels.",
        },
        "features": {
            "show_reward": False,
            "show_pass_rate": False,
            "show_tau2_eval": False,
            "show_high_stakes": False,
            "show_repeated_task_rewards": False,
            "show_product_storyboard": False,
            "show_track_comparison": False,
            "show_hermes_mode": True,
        },
    },
)
