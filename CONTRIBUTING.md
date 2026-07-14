# Contributing

## Setup

```bash
uv sync --dev                       # backend (xenon installs from the git pin)
cd frontend && npm install          # dashboard
cp .env.example .env                # optional; the demo needs no config
```

Run the app per [README.md](README.md); the invariants a change must respect
are listed in [AGENTS.md](AGENTS.md).

## Tests

| Tier | Command | Notes |
| --- | --- | --- |
| Hermetic | `uv run pytest` | default; no network/db/Modal, runs in CI |
| Plan contract | included in the default run | static xenon preflight of all workflow files |
| Live Modal | `PERSONA_AUDIT_LIVE_TESTS=1 uv run pytest -m modal_live` | **spends real GPU money**; needs `bootstrap_modal` completed; maintainers only, never in push/PR CI |

Please add tests with behavior changes: provider work under
`tests/test_registry.py` / `tests/test_trace_source.py`, score access under
`tests/test_score_access.py` / `tests/test_scores_io.py` (keep the
SQL/offline shapes in sync), factory work under `tests/factory/`.

## Style

`ruff` is the only linter/formatter (`uv run ruff check .` and
`uv run ruff format .`); CI enforces both. Long literal strings are fine
(E501 is off); let the formatter own layout. New env vars must be added to
`.env.example` — a hygiene test fails otherwise.

## Adding a data source

Follow the "Register Your Provider" walkthrough in
[docs/adapter-contract.md](docs/adapter-contract.md): one adapter under
`backend/adapters/`, one provider module under `backend/api/providers/`, one
registry entry, tests for loader shape and provider routing.

## Pull requests

- Keep PRs to one concern; include the why in the description.
- `uv run pytest && uv run ruff check . && (cd frontend && npm run build)`
  must pass.
- Don't commit `.env`, generated caches, Modal artifacts, or private data.
