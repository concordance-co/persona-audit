# Focus Group: Frontend Critique & Redesign Rationale

This document records a simulated focus-group pass over the dashboard
(branch `fable/focus-group`). Four personas walked the current UI against
all three data seeds; their critiques drove the changes on this branch.

Ground rules for the redesign that followed:

- Page set and navigation are frozen (Overview, Character, Tail, Sessions,
  Report, Registry, LLMs, Hermes Lab; three providers).
- Remix what is *on* the pages, not which pages exist.
- Simplify, never add net complexity.
- Reuse existing components, views, and aggregations first; new
  calculations only where no existing one serves the need.

## The personas

### 1. First-run Frankie — OSS evaluator, 10 minutes to a verdict

Cloned the repo, ran the demo, knows nothing about activation scores.
Their question: *"what is this product telling me?"*

- "Overview opens with two strips of raw baseline means and two z-score
  heatmaps. I don't know what a 'frozen global raw-activation basis' is.
  Nothing on the first screen states a finding."
- "The single best sentence in the app — 'Against control, Sol reads
  highest above on Warmth…' — is on the Character page, two clicks in.
  Why doesn't the landing page talk to me like that?"
- "The 'Deployment Preview Storyboard' says it is *example-only* and
  *block-sorted*. If the chart's own caption tells me not to trust it,
  why is it here?"
- "The Tail page is the moment I understood the product. It leads with a
  plain-English sentence, then a map. Everything should read like Tail."

### 2. Safety-lead Sam — alignment researcher triaging a model

Wants worst-case first, evidence links, minimal clicks to a transcript.

- "My workflow is: what's bad → which conversations → show me the turn.
  The product has all three surfaces but they aren't a spine. The
  Investigation Queue (the actual triage view) is below four charts of
  corpus-level baselines."
- "Sessions is where I expect to triage, and it's an unranked table. The
  risk pill is lexical flag heuristics — the activation evidence the
  product is *about* isn't in the list at all. I have to arrive from a
  deep link elsewhere to get a focused session view."
- "Character's six view modes are two too many. Frequency is the x-axis
  of Portrait; Track levels is Track deltas plus the control column that
  the heatmap below already shows."

### 3. Eng-lead Elena — product lead reading the tau2 seed

Thinks in pass rates, segments, and cost of failure.

- "The copy promises 'product analytics over an agent benchmark', but
  reward shows up only as a table column and a hero chip. The panels
  that told the product story — cohorts, interaction-length burden,
  segment queue — are dead exports wired to nothing."
- "The one thing I actually want — *does behavior predict failure?* — is
  computed (`workflow_outcome_deltas`, Cohen's d of each trait, failed
  vs passed sessions, per workflow) and shipped in the payload, and no
  page renders it. That's the tau2 exemplar view, already built, hidden."

### 4. Local-agent Harper — hobbyist auditing their own Hermes agent

- "Hermes Lab feels like a different app: its own tab bar, its own tone,
  and half the cards say 'pending' or 'what unlocks next'. The Overview
  tab repeats the Today tab with a bigger orb; the Character tab is a
  placeholder explaining what it might become."
- "The interesting thing about my data is that it's *real* trajectories
  with reasoning turns. The shared pages handle that fine — what I'm
  missing is a reason to look at any particular session first."

## Synthesis — three findings

1. **Lead with the finding, not the instrument.** Character and Tail
   already open with a plain-language sentence built from the data.
   Overview — the landing page — opens with instrumentation. Every
   headline the landing page needs is already computed (character
   signature, tail cluster count + worst mode, top outlier, outcome
   coupling, track separation).
2. **The triage spine is missing its middle.** Overview says "these
   traces are outliers", SessionDetail shows the evidence — but
   Sessions, the page between them, ranks nothing. The per-trace signal
   (`_workflow_outliers`: RMS-z outlier score + top deviating vector)
   already exists; it just isn't joined into the sessions payload.
3. **Cut what answers no question.** Global baseline strips (raw means,
   duplicated in heatmap tooltips), the example-only storyboard, two
   redundant Character modes, two redundant Hermes tabs, and four dead
   panel components.

## The changes on this branch

| Change | Persona need | Reuse |
| --- | --- | --- |
| Overview opens with a **Findings strip**: one headline card per question (character signature, tail risk, top outlier, dataset exemplar), each deep-linking to its page | Frankie, Sam | `signatureSummary`, `tailModeHeadline`, `joinTraits`, outlier queue rows — all existing exports; data from the three already-cached endpoints |
| Overview drops the baseline strips, the storyboard, and the separate stats grid; the two trait-detail cards merge into one with a family-spanning selector | Frankie | Existing `BaselineHeatmap`, `TraitDetailChart`, hero chips absorb the counts |
| **Sessions ranks by signal**: new `signal` block per row (outlier score, top deviating trait, z), sorted worst-first, deep-linking with focus context | Sam | Backend `_workflow_outliers` (existing computation, new join); frontend `deviationLabel` + `sessionFocusLink` |
| **Outcome ↔ behavior card** on Overview for reward-bearing datasets: renders `workflow_outcome_deltas` ("failed Cancel/refund sessions read more X, d=…") | Elena | Existing computed-but-hidden aggregation; existing card styles |
| Character modes 6 → 4 (drop Frequency and Track levels) | Sam | Portrait already encodes frequency; track heatmap already shows control levels |
| Hermes Lab tabs 5 → 3 (Today absorbs the mood timeline; placeholder Character tab and duplicate Overview tab removed) | Harper | Existing orb + timeline components |
| Delete dead exports: `CohortExplorerPanel`, `TurnLengthPanel`, `ProductStateCards`, `SegmentQueuePanel`, unused API wrappers | all | net deletion |

Per-dataset exemplars, all through shared components:

- **persona_demo** — Persona separation mode + track findings headline
  (the paired-seeds contrast is the headline sentence).
- **tau2** — Outcome ↔ behavior card + reward-aware findings headline
  (behavior coupled to task success).
- **hermes** — signal-ranked Sessions over real trajectories + the mood
  read in Hermes Lab (real reasoning traces are the story).
