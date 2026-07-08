"""Provider selection and display metadata for behavior-audit demos."""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Any


DEFAULT_PROVIDER_ENV = "BEHAVIOR_AUDIT_DEFAULT_PROVIDER"
PROVIDER_ENV = "BEHAVIOR_AUDIT_PROVIDER"

TAU2_PROVIDER = "tau2"
HERMES_PROVIDER = "hermes"
PERSONA_DEMO_PROVIDER = "persona_demo"
VALID_PROVIDERS = {TAU2_PROVIDER, HERMES_PROVIDER, PERSONA_DEMO_PROVIDER}


def resolve_provider(provider: str | None = None) -> str:
    raw = provider or os.environ.get(PROVIDER_ENV) or os.environ.get(DEFAULT_PROVIDER_ENV) or TAU2_PROVIDER
    normalized = str(raw).strip().lower().replace("_", "-")
    if normalized in {"tau2", "tau-2", "tau2-public-airline", "tau2-smoke"}:
        return TAU2_PROVIDER
    if normalized in {"hermes", "hermes-local", "hermes-smoke", "hermes-agent"}:
        return HERMES_PROVIDER
    if normalized in {"persona-demo", "persona-audit-demo", "demo", "personas"}:
        return PERSONA_DEMO_PROVIDER
    return TAU2_PROVIDER


@lru_cache(maxsize=4)
def provider_descriptor(provider: str | None = None) -> dict[str, Any]:
    provider_id = resolve_provider(provider)
    if provider_id == PERSONA_DEMO_PROVIDER:
        return {
            "id": PERSONA_DEMO_PROVIDER,
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
            },
        }
    if provider_id == HERMES_PROVIDER:
        return {
            "id": HERMES_PROVIDER,
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
                "show_hermes_mode": True,
            },
        }
    return {
        "id": TAU2_PROVIDER,
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
        },
    }
