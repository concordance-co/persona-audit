"""Turn-by-turn generation rounds.

The generation contract (docs/demo-dataset-build-plan.md) requires each track
to condition only on its own prior assistant turns plus the fixed user turns.
Because turn t+1's prompt depends on turn t's generation, a stage runs as a
sequence of rounds: round t generates assistant turn t for every (seed, track)
pair in one batched Modal workflow run.

This module is pure data plumbing: build the examples for a round, and fold a
round's generation rows back into per-track histories. The driver
(backend/scripts/demo_hillclimb.py) owns file I/O and workflow invocation.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from backend.demo.personas import PersonaPrompt
from backend.demo.seeds import SeedConversation

PROVIDER_ID = "persona_audit_demo"

# histories[(seed_id, track)] -> list of generated assistant turns so far
Histories = dict[tuple[str, str], list[str]]


def example_key(seed_id: str, track: str, turn_index: int) -> str:
    return f"demo_{seed_id}_{track}_t{turn_index:02d}"


def max_rounds(seeds: Sequence[SeedConversation]) -> int:
    return max(len(seed.user_turns) for seed in seeds)


def build_round_examples(
    seeds: Sequence[SeedConversation],
    prompts: Mapping[str, PersonaPrompt],
    histories: Histories,
    turn_index: int,
    *,
    stage: int,
) -> list[dict[str, Any]]:
    """Examples for one round: assistant turn ``turn_index`` for every seed x track."""

    examples: list[dict[str, Any]] = []
    for seed in seeds:
        if turn_index >= len(seed.user_turns):
            continue
        for track, prompt in prompts.items():
            history = histories.get((seed.seed_id, track), [])
            if len(history) != turn_index:
                raise ValueError(
                    f"history for {seed.seed_id}/{track} has {len(history)} turns; "
                    f"expected {turn_index} before generating turn {turn_index}"
                )
            messages: list[dict[str, str]] = [
                {"role": "system", "content": prompt.system_prompt}
            ]
            for prior in range(turn_index):
                messages.append({"role": "user", "content": seed.user_turns[prior]})
                messages.append({"role": "assistant", "content": history[prior]})
            messages.append({"role": "user", "content": seed.user_turns[turn_index]})
            examples.append(
                {
                    "key": example_key(seed.seed_id, track, turn_index),
                    "prompt": messages,
                    "labels": {
                        "provider_id": PROVIDER_ID,
                        "seed_id": seed.seed_id,
                        "paired_group_id": seed.seed_id,
                        "track": track,
                        "persona_prompt_id": prompt.prompt_id,
                        "sensitivity_tier": seed.sensitivity_tier,
                        "decision_type": seed.decision_type,
                        "turn_index": turn_index,
                        "stage": stage,
                    },
                    "metadata": {
                        "source_dataset": seed.source_dataset,
                        "public_provenance": seed.public_provenance,
                    },
                }
            )
    return examples


def apply_round_results(
    histories: Histories,
    seeds: Sequence[SeedConversation],
    prompts: Mapping[str, PersonaPrompt],
    turn_index: int,
    rows: Sequence[Mapping[str, Any]],
) -> Histories:
    """Fold one round's generation rows into histories. Fails loudly on gaps."""

    by_key = {str(row.get("example_key")): row for row in rows}
    for seed in seeds:
        if turn_index >= len(seed.user_turns):
            continue
        for track in prompts:
            key = example_key(seed.seed_id, track, turn_index)
            row = by_key.get(key)
            if row is None:
                raise KeyError(f"generation result missing for example {key}")
            text = str(row.get("generated_text", "")).strip()
            if not text:
                raise ValueError(f"empty generation for example {key}")
            histories.setdefault((seed.seed_id, track), []).append(text)
    return histories


def histories_to_json(histories: Histories) -> dict[str, list[str]]:
    return {f"{seed_id}::{track}": turns for (seed_id, track), turns in histories.items()}


def histories_from_json(payload: Mapping[str, Sequence[str]]) -> Histories:
    histories: Histories = {}
    for key, turns in payload.items():
        seed_id, _, track = key.partition("::")
        histories[(seed_id, track)] = list(turns)
    return histories
