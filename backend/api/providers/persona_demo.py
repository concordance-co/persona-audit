"""Persona-demo provider: the bundled Sol/Marrow/control dataset (no database).

This is the smallest provider module and the template for adding your own:
a loader returning :class:`TraceLoadResult`, a :class:`ScoreConfig`, and a
descriptor. See docs/adapter-contract.md.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from backend.api.models import AuditTrace
from backend.api.registry import ProviderSpec, ScoreConfig, TraceLoadResult
from backend.api.trace_io import load_traces
from backend.paths import REPO_ROOT, env_value, load_dotenv

PROVIDER_ID = "persona_audit_demo"
SOURCE_LABEL = "Persona Audit demo (Modal)"
TRACES_ENV = "PERSONA_AUDIT_DEMO_PRODUCT_TRACES"
DEFAULT_TRACES_PATH = REPO_ROOT / "data" / "demo" / "normalized_traces.json"

# Historical: the shipped demo score cache in data/supplemental_scores/ was
# produced by this run.
DEFAULT_RUN_ID = "wr_c325b34b511a_a9ce320d"


def _load_traces() -> TraceLoadResult:
    """Load the shipped persona-demo dataset from normalized AuditTrace JSON.

    Fully local, no database. Override the path with PERSONA_AUDIT_DEMO_PRODUCT_TRACES.
    Each trace is mapped onto the product's generic grouping dimensions so the
    existing UI browses by persona; see _shape_trace.
    """

    load_dotenv()
    configured = env_value(TRACES_ENV)
    path = Path(configured) if configured else DEFAULT_TRACES_PATH
    if not path.exists():
        return TraceLoadResult(traces=[], provider_id=PROVIDER_ID, source=SOURCE_LABEL)
    traces = [_shape_trace(trace) for trace in load_traces(path)]
    return TraceLoadResult(traces=traces, provider_id=PROVIDER_ID, source=SOURCE_LABEL)


def _shape_trace(trace: AuditTrace) -> AuditTrace:
    """Project persona labels onto the dimensions the analytics layer groups by.

    The product-analytics layer reads ``domain``, ``user_id`` and the
    ``metadata`` keys ``workflow``/``final_action``, never ``labels``. The
    demo's persona is in ``labels['track']``, so without this mapping every
    track collapses into one segment and Marrow/control are unreachable. This
    is presentation glue only — the shipped dataset keeps the persona in
    ``labels`` and is not modified.

    - domain / user_id / final_action -> track (Sol / Marrow / control), so the
      "Track" axis, the persona cohort page, and the sessions ``?domain=``
      filter all split three ways.
    - workflow -> decision_type, so the "decision type by persona" matrix
      carries the real decision types.
    - task_id is left as the seed id so the same seed answered by each track
      still groups as a paired/repeated task.
    """

    track = str(trace.labels.get("track") or "unknown")
    decision_type = str(trace.labels.get("decision_type") or "unknown")
    metadata = {**dict(trace.metadata), "workflow": decision_type, "final_action": track}
    return replace(trace, domain=track, user_id=track, metadata=metadata)


SPEC = ProviderSpec(
    key="persona_demo",
    aliases=frozenset({"persona-demo", "persona-audit-demo", "demo", "personas"}),
    alias_prefixes=("persona",),
    load_traces=_load_traces,
    local_only=True,
    score=ScoreConfig(
        run_id_env="PERSONA_AUDIT_DEMO_SCORE_RUN_ID",
        default_run_id=DEFAULT_RUN_ID,
        # Demo score rows share the tau2 score table/shape.
        table_env="PERSONA_AUDIT_SCORE_TABLE",
        default_table="persona_audit_tau2_score_rows",
    ),
    descriptor={
        "id": "persona_demo",
        "label": "Persona demo",
        "dataset_label": "Persona separation demo (Sol / Marrow / control)",
        "cohort_label": "Persona",
        "cohort_plural_label": "Personas",
        "domain_label": "Track",
        "segment_label": "Decision type",
        "action_label": "Track",
        "task_label": "Seed",
        "outcome_label": "Outcome",
        "reward_label": "Reward",
        "pass_rate_label": "Pass rate",
        "copy": {
            "overview_subtitle": "Contrastive persona demo: the same user turns answered by Sol, Marrow, and a plain control.",
            "overview_scope_title": "Demo scope",
            "overview_scope_note": "Synthetic paired dataset. Each seed conversation is answered by three persona tracks so the audit surfaces show persona separation, not production telemetry.",
            "overview_hero": "This view contrasts three assistant personas over identical user turns: how their trait posture and emotion read on the same decisions.",
            "storyboard_note": "Example-only: seeds are paired across the Sol / Marrow / control tracks.",
            "analytics_subtitle": "Persona tracks, decision types, and turn structure across the demo seeds.",
            "analytics_hero": "This dataset is built for contrast: one fixed set of user turns, three persona replies each, scored on the same surfaces.",
            "cohorts_subtitle": "The three persona tracks in the demo.",
            "cohort_detail_subtitle": "A persona track (Sol, Marrow, or control), not a production identity.",
            "repeated_task_note": "The same seed conversation answered by each persona track.",
        },
        "features": {
            "show_reward": False,
            "show_pass_rate": False,
            "show_tau2_eval": False,
            "show_high_stakes": True,
            "show_repeated_task_rewards": False,
            "show_product_storyboard": False,
            "show_track_comparison": True,
        },
    },
)
