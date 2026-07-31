# Shipped data

Everything tracked under `data/` is intended to be safe for public use.

- `demo/` is an in-house synthetic persona-separation dataset. Its methodology,
  contents, and redistribution statement are documented in `demo/README.md`.
- `score_summaries/` and the Tau2 supplemental score fixture are derived
  activation-score outputs over the public
  [Tau2 benchmark](https://github.com/sierra-research/tau2-bench), released by
  Sierra Research under the MIT License. They contain scored/aggregated rows,
  not private Concordance conversations.
- `supplemental_scores/` is also the default local sink for scores you create.
  Generated caches are gitignored; only explicitly allowlisted public fixtures
  are tracked.

Files under `reports/behavior_audit_public/local_smoke/` are small synthetic
smoke-test outputs built from the in-repo fixture traces.
