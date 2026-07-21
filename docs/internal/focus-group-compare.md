# Focus Group — Branch Comparison: `fable/focus-group` vs `codex/focus-group`

Written after both branches landed, before any merge edits. Both branches
were run live and screenshotted against all three providers. Companion to
`docs/internal/focus-group.md` (fable's personas) and `docs/focus-group.md`
(codex's personas, on its branch).

## TL;DR

The two focus groups **independently converged** on the same diagnosis:
the product's evidence is strong, the hierarchy is wrong — lead with the
finding, make the pages a review sequence, and turn Sessions into a
ranked queue. That convergence is the strongest signal either branch
produced; the direction is settled.

They diverge on **mechanism**:

- **fable** is *subtractive and analytic*: new backend signal join, hidden
  aggregations surfaced, weak panels deleted (net −236 frontend lines,
  +44 backend). No visual retheme.
- **codex** is *additive and presentational*: single-headline "lead" heroes
  with CTAs, a lexical-flag review queue, and a full visual reskin via a
  404-line override stylesheet (net +622 lines). No backend changes, no
  deletions.

Recommended merge: **fable as the skeleton** (backend signal, deletions,
outcome card, mode trims are structural and constraint-compliant),
**grafting codex's best presentational ideas** (Tail lead, Sessions
search/empty-state, CTA treatment, possibly the theme — properly, in
`styles.css`). Details below.

## Where we converged (adopt without debate)

| Idea | fable's form | codex's form |
| --- | --- | --- |
| Overview leads with a finding, not instruments | Findings strip: 3–5 cards (character, tail, outlier, dataset exemplar) | `OverviewLead`: one dataset-aware headline + CTA |
| Sessions becomes a ranked queue | Activation-signal ranking (backend join), focus deep-links | Risk/flag ranking (client-side), "Why review" column |
| Dataset exemplars via content, not forked UI | persona_demo→separation card, tau2→outcome coupling, hermes→character read | persona_demo→separation default + η² lead; hermes→setup pointer |
| The η²=0.96 separation stat is the persona_demo headline | Separation finding card | "Strongest separation" lead |
| Pages form a review sequence | "Triage spine": Overview → Sessions → SessionDetail | "Guided flow": Orient → Characterize → Inspect → Review → Summarize |

Two independent persona panels writing the same headline (down to both
picking η² on Assistant axis) is good evidence these are the right calls.

## The four real disagreements

### 1. What ranks the Sessions queue — the substantive one

- **codex** sorts by lexical risk band → flag count → turns. Live on tau2,
  the top ~12 rows all read "High risk · 3–4 flags"; 72 of 200 sessions
  are "high risk", so the band barely discriminates, and flags are the
  keyword heuristics — the *weakest* signal in the product.
- **fable** sorts by the activation outlier score (RMS-z vs segment
  baseline, reusing `_workflow_outliers`), with the top deviating trait
  and z shown per row, and each row deep-linking into Session Review
  focused on that signal.

The product's thesis is activation evidence; ranking its queue by keyword
flags undercuts the pitch. **Recommend fable's ranking as primary**, and —
per the repo's "combine = union" principle — keep codex's flag
information as a secondary cue (risk pill already survives on fable's
table; codex's "Why review" phrasing could become the pill's tooltip or a
tiebreaker sort). Also adopt codex's **search box and empty-state row**
outright; fable's table lacks both and they're cheap.

### 2. One lead vs. a findings strip

- **codex**: one big headline per page, one CTA. Decisive, calm, but
  discards the other findings (tail, outlier, outcome coupling never
  reach the Overview reader), and its fallback lead is computed from the
  currently-toggled segment rows, so flipping a toggle rewrites the
  "finding" — a lead that changes with a control reads as unstable.
- **fable**: 3–5 equal cards. More informative, every deep-dive page gets
  its hook, but codex's panel would fairly note it re-creates "several
  equally weighted things" at the top of the page.

**Recommend a hybrid**: keep fable's strip (it's the only place the
outcome coupling and tail headline surface on Overview) but adopt codex's
visual hierarchy — promote the dataset-exemplar card to a wider lead
position with codex's CTA arrow treatment, demote the rest to compact
cards. No new data needed; purely a layout pass.

### 3. Additive reskin vs. subtractive declutter

- **codex's theme is genuinely better-looking** (paper/ink, dark sidebar,
  soft coral accent — screenshots confirm it reads as a calmer
  professional tool than the red-brand shell), but the mechanism is an
  override stylesheet stacked on the 3,848-line `styles.css`: every
  future style change now fights a 404-line cascade. It also deletes
  nothing — the baseline strips, "example-only" storyboard, stats grid,
  six Character modes, and five Hermes tabs all survive under the new
  paint, even though codex's own focus-group doc complains about "too
  many equally weighted controls".
- **fable** removed those (strips, storyboard, dead panels/wrappers,
  mode + tab trims) but left the loud shell untouched — codex's panel
  would rightly call that a miss; visual noise was a real critique.

**Recommend**: keep fable's deletions; treat the theme as a separate
user decision, and if adopted, port codex's palette into the existing
`styles.css` tokens (`--brand-*`/`--surface-*` swap) instead of keeping
the override sheet. Marshall should eyeball both shells before deciding —
this is taste, not correctness.

### 4. Per-dataset default views

codex flips persona_demo's Overview default to the separation view
("best foot forward" for the flagship demo). That directly contradicts
the consistency rule from the frontend-unification pass (*same default
views everywhere, no per-dataset defaults*) which fable honored — fable
surfaces separation via the findings card + one click instead.
codex's version is arguably the better first impression; it's also the
rule being broken. **Marshall's call**; if the exception is granted it
should be documented as a deliberate amendment to the rule, not slipped
in.

## Scorecard against the stated constraints

| Constraint | fable | codex |
| --- | --- | --- |
| Pages/nav frozen | ✓ | ✓ (after second commit reverted its nav restructure) |
| Simplify, don't add complexity | ✓ net −236 lines, deletions | ✗ net +622 lines, override stylesheet, nothing removed |
| New aggregations allowed | signal join; surfaced `workflow_outcome_deltas` | none (client-side sorts of existing lexical fields) |
| Reuse best existing views | reused analytic machinery; deleted only dead/duplicative views | reused all views untouched; did not reach the strongest unused aggregations |
| Works across all 3 seeds | verified live ×3, graceful unscored-hermes degradation | verified live; hermes lead correctly points unscored sources to setup |

## Nits and bugs found while reviewing

**codex**
- Tail "Review exemplar" CTA passes `{ tail_mode: id }` to
  `sessionFocusLink`, a parameter SessionDetail never reads — the link
  opens the session *unfocused*, weaker than the existing exemplar links
  further down the same page (which pass coordinate/vector/turn). Easy
  fix in the merge: reuse the `TailExemplar` context.
- `row.overview !== false` filters track vectors on a field that doesn't
  exist in the payload (harmless no-op).
- Tail lead duplicates the concerning/benign stat cards directly below it.
- The `OverviewLead` "divergent segment" text depends on the active
  segment toggle (see disagreement 2).

**fable**
- Dropped the Flags column from Sessions entirely; flag info now lives
  only in the risk pill (codex's "Why review" phrasing is the better home
  for it).
- Overview now issues three fetches (product-analytics + character +
  tail). All are server-cached, but it's added first-paint latency codex
  doesn't have.
- Left the loud shell and Tail's opening untouched — both improved by
  codex.

## Proposed merge plan (for the joint round — no edits made yet)

Base: `fable/focus-group`. Steps, in order:

1. **Sessions**: graft codex's search input + empty-state row onto
   fable's signal-ranked table; move codex's "Why review" phrasing into
   the risk-pill tooltip or a secondary column; flags/risk as sort
   tiebreaker after outlier score.
2. **Tail**: add codex's lead section (headline + share sentence +
   exemplar CTA), but build the CTA link from the existing exemplar
   focus context; drop the stat cards it duplicates (net-zero clutter).
3. **Overview**: keep fable's findings strip + outcome card; restyle per
   codex's hierarchy (one promoted lead card with CTA, compact rest).
4. **Defaults**: Marshall decides persona_demo separation-by-default vs
   the consistency rule; either way, document it.
5. **Theme**: Marshall picks a shell. If codex's, port tokens into
   `styles.css` and delete `focus-group.css`; never ship the override
   sheet long-term.
6. **Docs**: fold both persona panels into one `docs/internal/`
   focus-group doc; the convergence table above is the summary.
7. Verify: pytest, ruff, `npm run build`, live pass over all three
   providers (including `PERSONA_AUDIT_HERMES_STATE_DB` demo-fallback
   path).
