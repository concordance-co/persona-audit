// LLMs page: copyable coding-agent context snippets.
// Moved verbatim from BehaviorAuditRoutes.jsx (pure reorganization).
import { useState } from 'react'

const LLM_CONTEXT_SNIPPETS = [
  {
    title: 'Use This Repo',
    body: `You are helping me use the Persona Audit repo.

This repo has a FastAPI backend in backend/ and a React dashboard in frontend/. Local .env values are private and should not be printed. Scoring workflows use the pinned Xenon Git dependency from pyproject.toml; follow README.md and AGENTS.md for install and update guidance.

Typical commands:
- Backend: uv run uvicorn backend.api.app:app --reload --port 8100
- Frontend: cd frontend && npm install && npm run dev
- Tests: uv run pytest
- Frontend build: cd frontend && npm run build

Start by checking README.md, AGENTS.md, and docs/adapter-contract.md. Then inspect backend/api/app.py, backend/api/trace_source.py, backend/api/scores/, and frontend/src/routes/behavior/ (pages/ has one file per route; frontend/README.md has the map).`,
  },
  {
    title: 'How It Works',
    body: `Persona Audit turns scored conversations into a small set of inspection surfaces.

The backend loads traces and score rows from a Postgres-compatible database when PERSONA_AUDIT_DATABASE_URL is configured, with bundled cache fallbacks for local demos. The legacy BEHAVIOR_AUDIT_DATABASE_URL and XENON_NEON_DATABASE_URL names are still supported. The backend computes global baselines, segment-level deltas, outlier queues, and session drilldowns. The frontend shows those outputs as overview cards, baseline heatmaps, detail charts, session pages, and registry metadata.

Read z-deltas as "how different this segment is from the global baseline." Zero is typical for the audited run. Positive means more of that trait or emotion family than baseline. Negative means less.`,
  },
  {
    title: 'Run On My Data',
    body: `I want to adapt Persona Audit to my own conversation data.

Help me identify:
1. The normalized trace schema in docs/adapter-contract.md and backend/api/models.py.
2. The score row schema expected by backend/api/scores/ and backend/scores_io.py.
3. Which fields are required for overview baselines, session drilldowns, and outlier queues.
4. Whether I should load from JSONL, local cache files, Postgres, or a new adapter.

Prefer small, reversible changes. Do not vendor scoring dependencies. If live data is needed, use .env variables by name only and never print secret values.`,
  },
  {
    title: 'Configure Postgres',
    body: `I want to configure Persona Audit with my own Postgres-compatible database.

Use PERSONA_AUDIT_DATABASE_URL as the primary DSN variable (BEHAVIOR_AUDIT_DATABASE_URL and XENON_NEON_DATABASE_URL are legacy aliases). Check backend/api/trace_source.py for trace loading, backend/api/scores/ for score loading, and backend/scripts for upload/import scripts.

Please verify whether the tables already exist before changing schema code. Upload scripts should create required tables when needed. Never print database credentials.`,
  },
  {
    title: 'Debug The Dashboard',
    body: `I am debugging the Persona Audit dashboard.

Please check the backend API response first, then the React view. Pages live in frontend/src/routes/behavior/pages/ (one file per route), shared labels/helpers are in frontend/src/routes/behavior/helpers.js, and the primary stylesheet is frontend/src/styles.css.

If the page has no live data, hit GET /api/health first — it reports the resolved provider, trace source, and score source. Then check whether .env exists and whether PERSONA_AUDIT_DATABASE_URL or PERSONA_AUDIT_TRACE_SOURCE=local is configured. If data loads but a chart is confusing, inspect the exact API fields used by the chart before changing labels or layout.`,
  },
  {
    title: 'Use Hermes Data',
    body: `I want to use local Hermes agent sessions in Persona Audit.

Hermes mode reads a local SQLite state database and maps sessions into the standard AuditTrace shape. Set PERSONA_AUDIT_PROVIDER=hermes or use ?provider=hermes in the dashboard. The adapter resolves PERSONA_AUDIT_HERMES_STATE_DB, then ~/.hermes/state.db, then falls back to the bundled demo sample in data/hermes_demo/ (override with PERSONA_AUDIT_HERMES_DEMO_TRACES).

Useful checks:
- uv run python -c "from backend.api.hermes import hermes_overview; print(hermes_overview()['inventory'])"
- backend/scripts/run_xenon_workflow.sh plan --file backend/workflows/hermes_scoring.py

Treat Hermes scores as proxy audit-model activations, not the agent's literal internals. Reasoning-based Thought-vs-Said views require captured reasoning spans and a Hermes scoring run.`,
  },
]

function CopySnippetButton({ text }) {
  const [copied, setCopied] = useState(false)
  function copy() {
    if (typeof navigator === 'undefined' || !navigator.clipboard) return
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true)
      window.setTimeout(() => setCopied(false), 1200)
    })
  }
  return (
    <button type="button" className="small-button" onClick={copy}>
      {copied ? 'Copied' : 'Copy'}
    </button>
  )
}

function LLMs() {
  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">LLMs</h1>
          <p className="subtle-line">Copy-paste context for working with this repo.</p>
        </div>
      </div>
      <div className="llm-snippet-grid">
        {LLM_CONTEXT_SNIPPETS.map(snippet => (
          <div key={snippet.title} className="card llm-snippet-card">
            <div className="card-heading-row">
              <div className="card-title">{snippet.title}</div>
              <CopySnippetButton text={snippet.body} />
            </div>
            <pre>{snippet.body}</pre>
          </div>
        ))}
      </div>
    </div>
  )
}

export { CopySnippetButton, LLM_CONTEXT_SNIPPETS, LLMs }
