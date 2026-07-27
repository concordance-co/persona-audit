"""Zero-code provider for normalized local JSON or JSONL conversation traces."""

from __future__ import annotations

from pathlib import Path

from backend.api.registry import ProviderSpec, ScoreConfig, TraceLoadResult
from backend.api.trace_io import load_traces
from backend.paths import env_value

TRACES_ENV = "PERSONA_AUDIT_LOCAL_TRACES"
PROVIDER_ID_ENV = "PERSONA_AUDIT_LOCAL_PROVIDER_ID"
LABEL_ENV = "PERSONA_AUDIT_LOCAL_LABEL"
CHARACTER_REFERENCE_ENV = "PERSONA_AUDIT_LOCAL_CHARACTER_REFERENCE"
WORKFLOW_DIMENSION_ENV = "PERSONA_AUDIT_LOCAL_WORKFLOW_DIMENSION"
ACTION_DIMENSION_ENV = "PERSONA_AUDIT_LOCAL_ACTION_DIMENSION"
COHORT_DIMENSION_ENV = "PERSONA_AUDIT_LOCAL_COHORT_DIMENSION"


def configured_provider_id() -> str:
    return (env_value(PROVIDER_ID_ENV, "local") or "local").strip()


def _load_traces() -> TraceLoadResult:
    provider_id = configured_provider_id()
    configured = env_value(TRACES_ENV)
    if not configured:
        return TraceLoadResult(
            traces=[],
            provider_id=provider_id,
            source=f"Local normalized traces ({TRACES_ENV} is not configured)",
        )
    path = Path(configured).expanduser()
    if not path.exists():
        raise FileNotFoundError(f"{TRACES_ENV} points to a missing file: {path}")
    return TraceLoadResult(
        traces=load_traces(path),
        provider_id=provider_id,
        source=f"Local normalized traces ({path})",
    )


def _label() -> str:
    return env_value(LABEL_ENV, "My local data") or "My local data"


SPEC = ProviderSpec(
    key="local",
    aliases=frozenset({"local", "local-data", "my-data"}),
    alias_prefixes=("local-",),
    load_traces=_load_traces,
    local_only=True,
    preferred_db_provider_id=configured_provider_id,
    score=ScoreConfig(
        run_id_env="PERSONA_AUDIT_LOCAL_SCORE_RUN_ID",
        default_run_id="local_unscored",
        table_env="PERSONA_AUDIT_LOCAL_SCORE_TABLE",
        # The canonical generic score-row shape currently lives in this
        # historical table name; the provider/run filters keep datasets isolated.
        default_table="persona_audit_tau2_score_rows",
    ),
    supports_reward_math=False,
    dimensions={
        "workflow": env_value(WORKFLOW_DIMENSION_ENV, "domain") or "domain",
        "final_action": env_value(ACTION_DIMENSION_ENV, "metadata.final_action") or "metadata.final_action",
        "cohort": env_value(COHORT_DIMENSION_ENV, "user_id") or "user_id",
    },
    character_reference_provider=env_value(CHARACTER_REFERENCE_ENV),
    descriptor={
        "id": "local",
        "label": _label(),
        "dataset_label": _label(),
        "cohort_label": "Cohort",
        "cohort_plural_label": "Cohorts",
        "domain_label": "Domain",
        "segment_label": "Domain",
        "action_label": "Action",
        "task_label": "Task",
        "outcome_label": "Outcome",
        "reward_label": "Reward",
        "pass_rate_label": "Pass rate",
        "copy": {
            "overview_subtitle": "Behavior analytics over your normalized local conversation data.",
            "overview_scope_title": "Local data scope",
            "overview_scope_note": "Loaded from a local JSON or JSONL file. Data remains on this machine.",
            "overview_hero": "Inspect behavior patterns, scored traits, and conversations in your own dataset.",
            "storyboard_note": "Trace order follows the normalized local file.",
            "analytics_subtitle": "Domains, cohorts, interaction length, and behavior signals.",
            "analytics_hero": "Start with the structure of your imported conversations, then inspect scored behavior.",
            "cohorts_subtitle": "Cohorts derived from normalized user and domain fields.",
            "cohort_detail_subtitle": "A cohort from your normalized local data.",
            "repeated_task_note": "Repeated normalized task identifiers.",
        },
        "features": {
            "show_reward": False,
            "show_pass_rate": False,
            "show_tau2_eval": False,
            "show_high_stakes": False,
            "show_repeated_task_rewards": False,
            "show_product_storyboard": False,
        },
    },
)
