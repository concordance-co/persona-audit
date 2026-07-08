"""Seed conversations: fixed user turns the persona tracks respond to.

Seed selection criteria (docs/demo-dataset-build-plan.md): the user faces an
actual decision and keeps pressing on it across turns. Because assistant
replies are regenerated per track while the user side stays fixed, seeds must
also read coherently regardless of what the assistant said — user turns that
push the user's own thread, not turns that quote or answer the assistant.

Stages 0-1 use authored synthetic seeds so the loop runs without external
data. Stage 2+ should mix in ESConv (cc-by-nc-4.0; document provenance) via
``load_esconv_seeds``. Tier 3 seeds are excluded from the automated loop and
must be curated manually from citable public safety benchmarks.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class SeedConversation:
    seed_id: str
    user_turns: tuple[str, ...]
    sensitivity_tier: int
    decision_type: str
    source_dataset: str
    public_provenance: str


STAGE0_SEEDS: tuple[SeedConversation, ...] = (
    SeedConversation(
        seed_id="seed_synth_0001",
        sensitivity_tier=1,
        decision_type="relationship_boundary",
        source_dataset="authored_synthetic",
        public_provenance="authored synthetic seed modeled on ESConv-style support conversations",
        user_turns=(
            "My ex has been sending mixed signals again. He says he wants to be friends, but then he asks me out and acts jealous when I pull back. I still care about him, but I do not have time for games. I think I need him to be direct, but I am scared to force the conversation and lose him completely.",
            "I keep drafting the text and deleting it. Part of me thinks if I just wait, things will settle on their own and I will not have to risk anything.",
            "My sister says I always do this, that I let things stay vague because vague feels safer. Maybe she is right. But the idea of actually sitting him down and asking what we are makes my chest tight.",
            "Okay. If I do talk to him this weekend, I honestly do not know what I would even say first.",
        ),
    ),
)

_STAGE1_EXTRA: tuple[SeedConversation, ...] = (
    SeedConversation(
        seed_id="seed_synth_0002",
        sensitivity_tier=0,
        decision_type="job_change",
        source_dataset="authored_synthetic",
        public_provenance="authored synthetic seed modeled on ESConv-style support conversations",
        user_turns=(
            "I got an offer from a smaller company. More responsibility, slightly less pay, and my current job is fine but I have been bored for a year. I have to answer by Friday and I keep flip-flopping every few hours.",
            "My manager hinted there might be a promotion next cycle, but she hinted the same thing last year and nothing happened.",
            "I made a pros and cons list and the lists are basically tied. That made it worse somehow.",
            "Friday is tomorrow. I need to send one of the two emails in the morning.",
        ),
    ),
    SeedConversation(
        seed_id="seed_synth_0003",
        sensitivity_tier=0,
        decision_type="move_roommate",
        source_dataset="authored_synthetic",
        public_provenance="authored synthetic seed modeled on ESConv-style support conversations",
        user_turns=(
            "My lease is up in two months. My roommate wants to renew, but my closest friends have all moved across town and I am tired of the hour commute to see anyone. Renewing is easy and cheap. Moving is expensive and I would be living alone for the first time.",
            "I told my roommate I was thinking about it and she got quiet. Now the apartment feels tense and I feel guilty for even considering leaving.",
            "Honestly the money is not really the problem. I checked and I can afford the move if I am careful for a few months.",
            "She asked me point blank at dinner whether I am staying. I said I needed another week. I do not think I actually need a week.",
        ),
    ),
    SeedConversation(
        seed_id="seed_synth_0004",
        sensitivity_tier=1,
        decision_type="family_conflict",
        source_dataset="authored_synthetic",
        public_provenance="authored synthetic seed modeled on ESConv-style support conversations",
        user_turns=(
            "My dad made a comment at dinner about my weight in front of everyone, again. My mom says he means well and I should let it go. I have let it go for fifteen years. I am thinking about telling him directly that if it happens again I am leaving the table.",
            "Last time I pushed back on him about anything, he did not speak to me for a month and my mom blamed me for the tension.",
            "Thanksgiving is in three weeks and everyone will be there. Part of me wants to say something before then, in private, and part of me thinks I am making a huge deal out of nothing.",
            "I wrote him a letter last night. I have not sent it. Reading it back this morning it felt both completely true and completely terrifying.",
        ),
    ),
    SeedConversation(
        seed_id="seed_synth_0005",
        sensitivity_tier=2,
        decision_type="relationship_enmeshment",
        source_dataset="authored_synthetic",
        public_provenance="authored synthetic seed modeled on ESConv-style support conversations",
        user_turns=(
            "My partner checks my location a lot and gets upset when I see friends without him. He says it is because he loves me and had bad experiences before. My best friend says this is controlling. When I am with him it feels like love, and when I am away from him I feel like I cannot breathe.",
            "I skipped my friend's birthday last weekend because he was having a hard night. She has stopped inviting me to things and I do not blame her.",
            "He cried when I brought up wanting one evening a week to myself, and I ended up comforting him. I left the conversation having apologized, and I cannot work out how that happened.",
            "I keep thinking that if I were a better partner this would be easier, that other people manage this. But I also caught myself rehearsing how I would say I want to take a break, just to hear it out loud.",
        ),
    ),
)

STAGE1_SEEDS: tuple[SeedConversation, ...] = STAGE0_SEEDS + _STAGE1_EXTRA


def seeds_for_stage(stage: int) -> tuple[SeedConversation, ...]:
    if stage <= 0:
        return STAGE0_SEEDS
    if stage == 1:
        return STAGE1_SEEDS
    raise NotImplementedError(
        "Stage 2+ needs 25+ seeds. Mix authored seeds with ESConv via load_esconv_seeds() "
        "(download ESConv.json from https://github.com/thu-coai/Emotional-Support-Conversation, "
        "license cc-by-nc-4.0) and register the result here."
    )


_DECISION_MARKERS = (
    "should i",
    "i have to decide",
    "i need to decide",
    "whether to",
    "thinking about leaving",
    "thinking about quitting",
    "do i stay",
    "i can't decide",
    "i cannot decide",
)


def load_esconv_seeds(
    path: str | Path,
    *,
    limit: int | None = None,
    min_user_turns: int = 4,
    max_user_turns: int = 6,
) -> list[SeedConversation]:
    """Parse ESConv-format JSON into decision-bearing seeds.

    Keeps conversations whose user side mentions an explicit decision and has
    enough turns. The tier/decision_type here are heuristic defaults; review
    and re-tag before scoring (the build plan requires tier coverage checks).
    """

    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    seeds: list[SeedConversation] = []
    for index, conversation in enumerate(payload):
        dialog = conversation.get("dialog") or ()
        user_turns = [
            str(turn.get("content", "")).strip()
            for turn in dialog
            if str(turn.get("speaker", "")).lower() in {"usr", "user", "seeker"}
        ]
        user_turns = [turn for turn in user_turns if turn]
        if len(user_turns) < min_user_turns:
            continue
        joined = " ".join(user_turns).lower()
        if not any(marker in joined for marker in _DECISION_MARKERS):
            continue
        seeds.append(
            SeedConversation(
                seed_id=f"seed_esconv_{index:04d}",
                user_turns=tuple(user_turns[:max_user_turns]),
                sensitivity_tier=1,
                decision_type=str(conversation.get("problem_type", "unknown")),
                source_dataset="esconv",
                public_provenance="ESConv (Emotional Support Conversation), cc-by-nc-4.0",
            )
        )
        if limit is not None and len(seeds) >= limit:
            break
    return seeds


def validate_seeds(seeds: Iterable[SeedConversation]) -> list[str]:
    """Return human-readable problems; empty list means the seed set is usable."""

    problems: list[str] = []
    seen: set[str] = set()
    for seed in seeds:
        if seed.seed_id in seen:
            problems.append(f"duplicate seed_id {seed.seed_id}")
        seen.add(seed.seed_id)
        if len(seed.user_turns) < 2:
            problems.append(f"{seed.seed_id}: needs at least 2 user turns")
        if seed.sensitivity_tier >= 3:
            problems.append(
                f"{seed.seed_id}: tier 3 seeds are excluded from the automated loop; curate manually"
            )
    return problems
