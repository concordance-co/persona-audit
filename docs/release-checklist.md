# Release Checklist

Use this before creating the public `persona-audit` repository or publishing a release branch.

## Privacy

- No `.env` files are tracked.
- No local Hermes state databases are tracked.
- No generated local score caches are tracked unless explicitly curated.
- Private source paths and machine-specific absolute paths are removed from docs and examples.
- Public fixtures have clear provenance and redistribution rights.

Suggested grep:

```bash
rg -n "\.env|XENON_NEON_DATABASE_URL|../xenon" \
  README.md AGENTS.md docs backend frontend/src tests .env.example pyproject.toml
```

Every match should be reviewed or removed before the first public commit.

## Setup

- `README.md` works from a fresh clone.
- `docs/agent-quickstart.md` is current.
- `docs/adapter-contract.md` matches `backend/api/models.py`.
- `BEHAVIOR_AUDIT_DATABASE_URL` is documented as the primary database variable.
- `XENON_NEON_DATABASE_URL` is documented only as a legacy compatibility alias.
- Xenon dependency points to a pushed Git commit or tag and installs without a sibling checkout.

## Verification

```bash
uv run pytest
uv run python -m py_compile \
  backend/api/app.py \
  backend/api/trace_source.py \
  backend/api/neon_scores.py \
  backend/scripts/upload_local_data_to_neon.py \
  backend/scripts/upload_tau2_scores_to_neon.py \
  backend/scripts/upload_hermes_scores_to_neon.py \
  backend/workflows/tau2_scoring.py \
  backend/workflows/hermes_scoring.py
uv run python -m pipelines_v2.cli workflow plan --file backend/workflows/tau2_scoring.py
uv run python -m pipelines_v2.cli workflow plan --file backend/workflows/hermes_scoring.py
cd frontend && npm run build
```

## Public Demo Data

- Default no-env demo loads without private data.
- Demo data is small and inspectable.
- Demo data uses the same adapter path users will use.
- Dashboard pages render useful content without requiring a database.

