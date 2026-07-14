# Release Checklist

Use this before publishing the public repository, a release branch, or a fork
that carries your own data.

## Privacy

- No `.env` files are tracked.
- No local Hermes state databases are tracked.
- No generated local score caches are tracked unless explicitly curated
  (the two allowlisted fixtures in `data/supplemental_scores/` are intended).
- Private source paths, machine-specific absolute paths, and internal
  infrastructure names are absent from docs and examples.
- Public fixtures have clear provenance and redistribution rights.

Suggested grep (every match should be reviewed before the first public commit):

```bash
rg -n "\.env|XENON_NEON_DATABASE_URL|yora|ap-[A-Za-z0-9]{20,}" \
  README.md AGENTS.md docs backend factory frontend/src tests .env.example pyproject.toml
```

## Setup

- `README.md` works from a fresh clone (see Verification below).
- `docs/adapter-contract.md` matches `backend/api/models.py` and the
  provider-registration walkthrough matches `backend/api/registry.py`.
- `PERSONA_AUDIT_DATABASE_URL` is documented as the primary database variable;
  `BEHAVIOR_AUDIT_*` / `XENON_NEON_DATABASE_URL` only as deprecated aliases.
- The xenon dependency points to a pushed Git commit and installs without a
  sibling checkout (`uv sync` in a clean environment).

## Verification

```bash
uv run pytest                       # hermetic + plan tiers
uv run ruff check . && uv run ruff format --check .
cd frontend && npm run build
```

Release gate (maintainers, costs real GPU money):

```bash
uv run python -m backend.scripts.bootstrap_modal --check
PERSONA_AUDIT_LIVE_TESTS=1 uv run pytest -m modal_live
```

Fresh-clone dry run in a clean directory: `uv sync && uv run pytest`, start
the backend, `npm install && npm run dev`, and confirm the Persona demo
renders with zero configuration.

## Public Demo Data

- Default no-env demo loads without private data.
- Demo data is small and inspectable and uses the same adapter path users
  will use.
- Dashboard pages render useful content without requiring a database.

## Deferred (post-release candidates)

- Trim or externalize the ~11 MB tau2 supplemental/summary fixtures if the
  persona demo becomes the sole showcase.
- Optional `persona-audit[scoring]` dependency extra: the serving layer
  already isolates `papers.voice` behind `backend/api/paper_assets.py`, so
  making xenon optional for dashboard-only installs is a packaging-only change.
