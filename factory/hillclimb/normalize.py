"""Convert generated track histories into normalized AuditTrace rows.

One trace per (seed, track): user/assistant turns interleaved, with the
metadata required by docs/demo-dataset-build-plan.md carried on the trace so
the scoring workflow and the shipped demo artifacts can support paired
comparison and public provenance.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from backend.api.models import AuditTrace, AuditTurn
from backend.api.trace_io import load_traces, save_traces
from backend.workflows.common import MODEL_ID
from factory.hillclimb.personas import PersonaPrompt
from factory.hillclimb.rounds import PROVIDER_ID, Histories
from factory.hillclimb.seeds import SeedConversation

__all__ = ["traces_from_histories", "load_traces", "save_traces"]


def traces_from_histories(
    seeds: Sequence[SeedConversation],
    prompts: Mapping[str, PersonaPrompt],
    histories: Histories,
    *,
    generation_params: Mapping[str, Any],
) -> list[AuditTrace]:
    traces: list[AuditTrace] = []
    for seed in seeds:
        for track, prompt in prompts.items():
            assistant_turns = histories.get((seed.seed_id, track))
            if not assistant_turns:
                continue
            turns: list[AuditTurn] = []
            index = 0
            for turn_pos, assistant_text in enumerate(assistant_turns):
                turns.append(
                    AuditTurn(
                        turn_id=f"{seed.seed_id}_{track}_u{turn_pos:02d}",
                        role="user",
                        content=seed.user_turns[turn_pos],
                        index=index,
                    )
                )
                index += 1
                turns.append(
                    AuditTurn(
                        turn_id=f"{seed.seed_id}_{track}_a{turn_pos:02d}",
                        role="assistant",
                        content=assistant_text,
                        index=index,
                    )
                )
                index += 1
            traces.append(
                AuditTrace(
                    trace_id=f"{seed.seed_id}__{track}",
                    session_id=f"{seed.seed_id}__{track}",
                    user_id=seed.seed_id,
                    domain="persona_demo",
                    task_id=seed.seed_id,
                    outcome="generated",
                    reward=None,
                    source_model=MODEL_ID,
                    user_model="fixed_seed_user",
                    turns=tuple(turns),
                    labels={
                        "provider_id": PROVIDER_ID,
                        "seed_id": seed.seed_id,
                        "paired_group_id": seed.seed_id,
                        "track": track,
                        "persona_prompt_id": prompt.prompt_id,
                        "sensitivity_tier": seed.sensitivity_tier,
                        "decision_type": seed.decision_type,
                    },
                    metadata={
                        "source_dataset": seed.source_dataset,
                        "public_provenance": seed.public_provenance,
                        "generation_model": MODEL_ID,
                        "generation_params": dict(generation_params),
                    },
                )
            )
    return traces
