"""Convert generated track histories into normalized AuditTrace rows.

One trace per (seed, track): user/assistant turns interleaved, with the
metadata required by docs/demo-dataset-build-plan.md carried on the trace so
the scoring workflow and the shipped demo artifacts can support paired
comparison and public provenance.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from backend.api.models import AuditTrace, AuditTurn
from backend.demo.personas import PersonaPrompt
from backend.demo.rounds import Histories, PROVIDER_ID
from backend.demo.seeds import SeedConversation
from backend.workflows.common import MODEL_ID


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


def save_traces(traces: Sequence[AuditTrace], path: str | Path) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps([trace.to_dict() for trace in traces], indent=2, sort_keys=True),
        encoding="utf-8",
    )


def load_traces(path: str | Path) -> list[AuditTrace]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    traces: list[AuditTrace] = []
    for row in payload:
        turns = tuple(
            AuditTurn(
                turn_id=str(turn["turn_id"]),
                role=str(turn["role"]),
                content=str(turn["content"]),
                index=int(turn["index"]),
                tool_name=turn.get("tool_name"),
                reasoning=turn.get("reasoning"),
                timestamp=turn.get("timestamp"),
            )
            for turn in row.get("turns", ())
        )
        traces.append(
            AuditTrace(
                trace_id=str(row["trace_id"]),
                session_id=str(row["session_id"]),
                user_id=str(row["user_id"]),
                domain=str(row["domain"]),
                task_id=str(row["task_id"]),
                outcome=str(row["outcome"]),
                reward=row.get("reward"),
                source_model=str(row["source_model"]),
                user_model=str(row["user_model"]),
                turns=turns,
                labels=dict(row.get("labels", {})),
                metadata=dict(row.get("metadata", {})),
            )
        )
    return traces
