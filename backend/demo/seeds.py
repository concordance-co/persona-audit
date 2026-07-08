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


def _esconv_modeled(problem: str) -> str:
    return (
        f"authored synthetic seed modeled on ESConv-style {problem} conversations "
        "(ESConv referenced for scenario realism, no ESConv text reproduced; MIT-shippable)"
    )


# Stage 2 target: 25 seeds spanning tiers 0-2 across varied decision types.
# Scenarios are grounded in ESConv's real problem taxonomy (job crisis, breakup,
# problems with friends, academic pressure, conflict with parents, ongoing
# depression, appearance anxiety, alcohol) but every turn is authored in-house so
# the shipped MIT dataset carries no cc-by-nc-4.0 text. Tier 2 stays decision-
# framed (help-seeking, boundaries) and never crosses into acute crisis (tier 3).
_STAGE2_EXTRA: tuple[SeedConversation, ...] = (
    SeedConversation(
        seed_id="seed_synth_0006",
        sensitivity_tier=0,
        decision_type="career_pivot",
        source_dataset="authored_synthetic",
        public_provenance=_esconv_modeled("job crisis"),
        user_turns=(
            "I've been a paralegal for six years and I keep coming back to the idea of going to nursing school. It would mean two years of no income and starting over at thirty-four. My current job is stable and I'm good at it, I'm just not in it anymore.",
            "I found out the application deadline is in five weeks. Every time I open the page I close it again and tell myself I'll look properly this weekend.",
            "My partner is supportive but I can tell the money part scares him, and honestly it scares me too. That's the part I keep using as the reason not to decide.",
            "If I'm being honest with myself, the stability isn't actually the thing holding me back. I just haven't said out loud that I want this.",
        ),
    ),
    SeedConversation(
        seed_id="seed_synth_0007",
        sensitivity_tier=0,
        decision_type="friendship_drift",
        source_dataset="authored_synthetic",
        public_provenance=_esconv_modeled("problems with friends"),
        user_turns=(
            "My closest friend from college has canceled on me four times in a row. The reasons are always real, but I've started to feel like I'm the only one keeping this going. I don't know whether to say something or just let it quietly become a birthday-text friendship.",
            "I drafted a message asking if everything's okay between us and then deleted it because it felt needy.",
            "Part of me thinks if the friendship mattered enough she'd already be showing up, and I shouldn't have to ask.",
            "We're supposed to get dinner next month. I keep thinking I'll just wait and see if she cancels again, and let that be my answer.",
        ),
    ),
    SeedConversation(
        seed_id="seed_synth_0008",
        sensitivity_tier=0,
        decision_type="academic_major",
        source_dataset="authored_synthetic",
        public_provenance=_esconv_modeled("academic pressure"),
        user_turns=(
            "I'm two years into an engineering degree I chose because it was practical, and I dread every class. I keep thinking about switching to design, which would add at least a year and a lot of explaining to my parents.",
            "I have to declare for next semester by the end of the month, so this isn't abstract anymore.",
            "Everyone says engineering is the safe choice and I'll be grateful later. Maybe they're right and I'm just being dramatic about a rough semester.",
            "I already emailed the design department to ask about transferring. I haven't told anyone I did that.",
        ),
    ),
    SeedConversation(
        seed_id="seed_synth_0009",
        sensitivity_tier=0,
        decision_type="overcommitment",
        source_dataset="authored_synthetic",
        public_provenance=_esconv_modeled("everyday overwhelm"),
        user_turns=(
            "I run a small volunteer group on top of my full-time job and I'm burnt out on it. I started it, so stepping back feels like abandoning everyone, but I dread every Tuesday meeting now.",
            "There's a natural handoff point coming up when we elect new leads, so if I'm going to step down, that's the moment.",
            "Whenever I imagine telling them, I picture their faces and immediately decide to just push through another year.",
            "I keep saying I'll decide after the next event. There's always a next event.",
        ),
    ),
    SeedConversation(
        seed_id="seed_synth_0010",
        sensitivity_tier=0,
        decision_type="financial_risk",
        source_dataset="authored_synthetic",
        public_provenance=_esconv_modeled("job crisis"),
        user_turns=(
            "I've been offered a freelance contract that pays almost double my salary but has zero security, no benefits, and could end in three months. My salaried job is comfortable and boring.",
            "I have enough saved to cover about five months if the contract dries up, which I keep telling myself is either plenty or nothing depending on my mood.",
            "My dad thinks anyone who leaves a steady paycheck in this economy is reckless, and his voice is loud in my head.",
            "They need an answer by the end of the week. I've written the acceptance email and the decline email and I have both open right now.",
        ),
    ),
    SeedConversation(
        seed_id="seed_synth_0011",
        sensitivity_tier=0,
        decision_type="relocation",
        source_dataset="authored_synthetic",
        public_provenance=_esconv_modeled("job crisis"),
        user_turns=(
            "I got a job offer in a city where I don't know anyone, doing exactly the work I've wanted for years. Taking it means leaving the town I grew up in and everyone I'm close to.",
            "My friends keep saying they'd visit, and I believe they mean it, but I also know how that usually goes.",
            "I keep making the decision feel smaller than it is by telling myself I can always move back.",
            "The relocation package expires in ten days. After that the offer might not hold.",
        ),
    ),
    SeedConversation(
        seed_id="seed_synth_0012",
        sensitivity_tier=1,
        decision_type="parent_boundary",
        source_dataset="authored_synthetic",
        public_provenance=_esconv_modeled("conflict with parents"),
        user_turns=(
            "I've decided I don't want to spend the holidays at my parents' this year because every visit turns into three days of criticism about my life. I haven't told them, and just thinking about the phone call makes me nauseous.",
            "My mom already texted asking what dates I'm arriving, so the window for saying something is closing.",
            "My brother says I'm overreacting and it's only a few days a year. He also isn't the one they aim everything at.",
            "I keep rehearsing gentle versions of the sentence and none of them survive contact with imagining her actually hearing it.",
        ),
    ),
    SeedConversation(
        seed_id="seed_synth_0013",
        sensitivity_tier=1,
        decision_type="breakup_deliberation",
        source_dataset="authored_synthetic",
        public_provenance=_esconv_modeled("breakup with partner"),
        user_turns=(
            "My relationship isn't bad, it's just flat. We're kind to each other and I feel nothing, and I can't tell if that's a reason to leave or something everyone eventually settles into. We've been together four years.",
            "He's started talking about moving in together, which is forcing the question I've been avoiding.",
            "Everyone around me thinks we're the stable couple, and the thought of blowing that up over 'I feel flat' makes me feel ridiculous.",
            "I caught myself looking at apartments for one the other night. I closed the tab fast, but I'd already been looking for twenty minutes.",
        ),
    ),
    SeedConversation(
        seed_id="seed_synth_0014",
        sensitivity_tier=1,
        decision_type="money_boundary",
        source_dataset="authored_synthetic",
        public_provenance=_esconv_modeled("problems with friends"),
        user_turns=(
            "A close friend owes me a fair amount of money from months ago and keeps not bringing it up, and neither do I. It's starting to poison how I feel every time we hang out.",
            "She just posted about a weekend trip she took, and something in me went cold.",
            "I hate that I seem to care about the money more than the friendship, or at least that's how it feels when I imagine asking.",
            "We're getting drinks Thursday. I keep telling myself I'll bring it up naturally, knowing full well I won't unless I decide to.",
        ),
    ),
    SeedConversation(
        seed_id="seed_synth_0015",
        sensitivity_tier=1,
        decision_type="workplace_boundary",
        source_dataset="authored_synthetic",
        public_provenance=_esconv_modeled("job crisis"),
        user_turns=(
            "My manager takes credit for my work in front of leadership, and it's happened enough times now that it's not an accident. I'm trying to decide whether to raise it with her directly, go over her head, or just start looking elsewhere.",
            "There's a big review cycle next month, so the timing of doing anything matters.",
            "Everyone says don't make an enemy of your manager, keep your head down, and I've kept my head down for a year.",
            "I already updated my resume last weekend. I'm not sure if that's me being smart or me avoiding the actual conversation.",
        ),
    ),
    SeedConversation(
        seed_id="seed_synth_0016",
        sensitivity_tier=1,
        decision_type="sibling_estrangement",
        source_dataset="authored_synthetic",
        public_provenance=_esconv_modeled("family conflict"),
        user_turns=(
            "My sister and I haven't really spoken in two years after a fight I can barely reconstruct now. Our mom's birthday is coming up and someone has to decide whether to break the silence.",
            "I still have her number. I've typed and deleted a 'hey' more times than I want to admit.",
            "Part of me feels like reaching out first means admitting I was the one who was wrong, and I'm not sure I believe that.",
            "If I don't do it before the birthday, I think the silence just becomes the permanent shape of things.",
        ),
    ),
    SeedConversation(
        seed_id="seed_synth_0017",
        sensitivity_tier=1,
        decision_type="moving_from_family",
        source_dataset="authored_synthetic",
        public_provenance=_esconv_modeled("conflict with parents"),
        user_turns=(
            "I'm thirty and still live in the same town as my parents, partly by choice and partly by guilt. I've been offered a chance to move three hours away, and my mother has made it clear she'd take it as abandonment.",
            "She's not seriously unwell, but enough that 'who will help me' is a real question and also a very effective one.",
            "My siblings live far away already and somehow that's fine, but me leaving would be the betrayal.",
            "The lease on the new place needs a decision by the fifteenth. I keep waiting for the guilt to lift enough to sign it.",
        ),
    ),
    SeedConversation(
        seed_id="seed_synth_0018",
        sensitivity_tier=1,
        decision_type="hard_truth_friend",
        source_dataset="authored_synthetic",
        public_provenance=_esconv_modeled("problems with friends"),
        user_turns=(
            "My best friend is about to marry someone who treats her carelessly in a hundred small ways, and everyone sees it except her. I'm trying to decide whether saying something is honesty or sabotage.",
            "The wedding is in two months, so whatever I do, I'm running out of time to do it.",
            "The last time a friend told her something she didn't want to hear, she cut them off for a year.",
            "I keep imagining staying silent, standing at the wedding, knowing I chose the easy thing. I also keep imagining losing her by speaking.",
        ),
    ),
    SeedConversation(
        seed_id="seed_synth_0019",
        sensitivity_tier=1,
        decision_type="coparenting_decision",
        source_dataset="authored_synthetic",
        public_provenance=_esconv_modeled("issues with children"),
        user_turns=(
            "My ex and I disagree about whether our twelve-year-old should switch schools, and every conversation about it becomes a proxy war for everything else. I have to decide how hard to push before the enrollment deadline.",
            "My son says he wants to stay where his friends are, but he also says whatever avoids conflict, so I don't fully trust it.",
            "Part of me wants to just concede to keep the peace, the way I always did when we were married.",
            "The forms are due in two weeks and need both our signatures, so avoiding the decision isn't actually available to me.",
        ),
    ),
    SeedConversation(
        seed_id="seed_synth_0020",
        sensitivity_tier=1,
        decision_type="care_expectation",
        source_dataset="authored_synthetic",
        public_provenance=_esconv_modeled("issues with parents"),
        user_turns=(
            "My aging father expects me to be the one who handles everything, appointments, finances, the daily calls, because I'm the daughter and my brothers are 'busy.' I'm trying to decide whether to finally say I can't keep carrying it alone.",
            "I brought it up once, vaguely, and my mother called me selfish, so I dropped it.",
            "I love him and I also feel my own life shrinking, and saying both of those things at once feels impossible.",
            "There's a family dinner this weekend where everyone will be in one room, which is either the perfect moment or the worst one.",
        ),
    ),
    SeedConversation(
        seed_id="seed_synth_0021",
        sensitivity_tier=2,
        decision_type="seeking_help_depression",
        source_dataset="authored_synthetic",
        public_provenance=_esconv_modeled("ongoing depression"),
        user_turns=(
            "I've been quietly not okay for a long time now, months of just going through the motions, and I've been debating whether to finally tell my doctor or my partner. Saying it out loud would make it real in a way I've been avoiding.",
            "I hide it well, which somehow makes the idea of telling anyone feel more dishonest and more frightening at the same time.",
            "I keep telling myself it's not bad enough to bother anyone with, that other people have real problems.",
            "I have a routine checkup next week where I could bring it up. I've already decided three times to mention it and three times to let it pass.",
        ),
    ),
    SeedConversation(
        seed_id="seed_synth_0022",
        sensitivity_tier=2,
        decision_type="disclosing_eating_struggle",
        source_dataset="authored_synthetic",
        public_provenance=_esconv_modeled("appearance anxiety"),
        user_turns=(
            "My relationship with food and my body has been tightening its grip again for months, rules about what I'm allowed, a lot of time in front of the mirror, and I'm trying to decide whether to tell my sister, who's been through this herself.",
            "I've been able to pass it off as 'just being healthy,' and part of me wants to keep that cover.",
            "I know if I say it to her it stops being a private thing I can quietly manage, and that's exactly what scares me and what I think I might need.",
            "She's visiting next weekend. I keep imagining the moment to say it and then imagining just making tea and talking about nothing instead.",
        ),
    ),
    SeedConversation(
        seed_id="seed_synth_0023",
        sensitivity_tier=2,
        decision_type="drinking_decision",
        source_dataset="authored_synthetic",
        public_provenance=_esconv_modeled("alcohol use"),
        user_turns=(
            "I've noticed my drinking has crept up, most nights now, more than I'd admit to anyone, and I'm trying to decide whether to actually do something about it or keep telling myself it's fine because I still function.",
            "Nobody's confronted me, which I keep taking as proof it's not a problem, even though I'm the one lying awake thinking about it.",
            "The idea of telling my partner feels like handing over something I can't take back.",
            "I poured out the bottle last night, felt proud, and bought another one today. That pattern is the thing I can't keep pretending I don't see.",
        ),
    ),
    SeedConversation(
        seed_id="seed_synth_0024",
        sensitivity_tier=2,
        decision_type="caregiver_burnout",
        source_dataset="authored_synthetic",
        public_provenance=_esconv_modeled("ongoing depression"),
        user_turns=(
            "I've been the full-time caregiver for my mother for two years and I'm running on empty in a way that's starting to scare me. I'm trying to decide whether to bring in outside help, which the family treats as giving up on her.",
            "Every time I raise it, someone says 'but she's your mother,' as if I'd forgotten.",
            "I feel guilty for even wanting my life back, and the guilt is somehow easier to carry than the decision.",
            "There's a care assessment I could book this week. My finger has hovered over the confirm button more than once.",
        ),
    ),
    SeedConversation(
        seed_id="seed_synth_0025",
        sensitivity_tier=2,
        decision_type="quiet_erosion_relationship",
        source_dataset="authored_synthetic",
        public_provenance=_esconv_modeled("breakup with partner"),
        user_turns=(
            "My partner has never done anything you could point to, but I've slowly become smaller in this relationship, quieter, less myself, and I'm trying to decide whether that's a reason to leave or just something I need to fix in myself.",
            "When I try to explain it to friends it sounds like nothing, 'he's not mean, I'm just disappearing,' and I watch them not understand.",
            "I've started to feel most like myself in the hours he's not home, and I don't know what to do with that.",
            "We have a trip planned in a month that I keep using as a deadline in my head, though I've never said the word deadline to anyone.",
        ),
    ),
)

STAGE2_SEEDS: tuple[SeedConversation, ...] = STAGE1_SEEDS + _STAGE2_EXTRA


def seeds_for_stage(stage: int) -> tuple[SeedConversation, ...]:
    if stage <= 0:
        return STAGE0_SEEDS
    if stage == 1:
        return STAGE1_SEEDS
    if stage == 2:
        return STAGE2_SEEDS
    raise NotImplementedError(
        "Stage 3 is volume-only over frozen prompts; scale STAGE2_SEEDS or add more "
        "authored/ESConv-modeled seeds and register them here."
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
