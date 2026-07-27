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

Start by reading README.md, AGENTS.md, frontend/README.md, and docs/adapter-contract.md. The route table is frontend/src/routes/BehaviorAuditRoutes.jsx; page implementations are in frontend/src/routes/behavior/pages/, with reusable charts and panels beside them.`,
  },
  {
    title: 'How It Works',
    body: `Persona Audit turns scored conversations into a small set of inspection surfaces.

Providers define how traces load, how dimensions map, which score run to use, and what the frontend exposes. The bundled persona_demo provider is fully offline. The zero-code local provider accepts normalized JSON or JSONL through PERSONA_AUDIT_LOCAL_TRACES. Postgres is optional.

Scored views need canonical rows keyed by score_family, coordinate, trace_id, and turn_index. The backend computes global baselines, segment deltas, matched-track comparisons, outlier queues, Character, Tail, and session drilldowns. The frontend composes those deterministic payloads.

Read z-deltas as "how different this segment is from the global baseline." Zero is typical for the audited run. Positive means more of that trait or emotion family than baseline. Negative means less.`,
  },
  {
    title: 'Run On My Data',
    body: `I want to adapt Persona Audit to my own conversation data.

Read docs/llm-data-conversion-instructions.md and docs/adapter-contract.md. Inspect my source schema and representative records, then:
1. Convert one conversation per object into normalized JSONL.
2. Preserve stable IDs, turn order, roles, timestamps, and useful low-cardinality labels.
3. Run: uv run python -m backend.scripts.validate_traces <output.jsonl>
4. Set PERSONA_AUDIT_LOCAL_TRACES=<output.jsonl>.
5. Open http://localhost:5173/?provider=local and verify /api/health?provider=local.

Use the zero-code local provider first. Create a reusable provider only if I need source-specific parsing or custom workflow/action/cohort mappings. Do not invent scores, print secrets, or retain private reasoning unless I explicitly opt in.`,
  },
  {
    title: 'Configure Postgres',
    body: `I want to configure Persona Audit with my own Postgres-compatible database.

Use PERSONA_AUDIT_DATABASE_URL as the primary DSN variable (legacy aliases exist only for migration). Check backend/api/registry.py and the active provider's ScoreConfig before assuming table or run names. Use backend/scripts/upload_local_data.py for normalized traces plus curated local score bundles.

Please verify whether the tables already exist before changing schema code. Upload scripts should create required tables when needed. Never print database credentials.`,
  },
  {
    title: 'Debug The Dashboard',
    body: `I am debugging the Persona Audit dashboard.

Please check /api/health?provider=<provider> and the affected API payload first, then the React view. The route table is frontend/src/routes/BehaviorAuditRoutes.jsx; pages live in frontend/src/routes/behavior/pages/, reusable panels in behavior/panels.jsx, data shaping in behavior/helpers.js, and styling in frontend/src/styles.css.

For my own local file, check PERSONA_AUDIT_LOCAL_TRACES and use ?provider=local. For a database-backed provider, check PERSONA_AUDIT_DATABASE_URL by name without printing its value. If data loads but a chart is empty, compare the provider's score inventory with the exact coordinates consumed by that component before changing layout.`,
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
