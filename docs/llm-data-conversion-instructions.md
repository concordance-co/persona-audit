# LLM Data Conversion Instructions

Use this template when a coding agent needs to adapt a new conversation dataset for Persona Audit.

## Task

Convert the provided conversation data into Persona Audit's normalized trace shape.

## Before Editing

1. Read `docs/adapter-contract.md`.
2. Inspect the source data schema and a few representative records.
3. Identify conversation/session boundaries.
4. Identify stable IDs for conversations, users, messages, and turns.
5. Identify role labels, timestamps, model names, source labels, outcome fields, and useful metadata.
6. Decide whether the data should be exposed through a small source-specific adapter or uploaded into Postgres-compatible trace tables.

## Output Requirements

- Emit one normalized JSON object per conversation/session when producing JSONL.
- Match the `AuditTrace` / `AuditTurn` shape documented in `docs/adapter-contract.md`.
- Preserve stable source IDs when available.
- Use deterministic fallback IDs when source IDs are missing.
- Preserve message order with zero-based `turn.index` values.
- Map source roles into simple roles such as `user`, `assistant`, `system`, or `tool`.
- Put source-specific fields in `labels` or `metadata`, not in ad hoc top-level fields.
- Keep credentials, API keys, access tokens, and secrets out of the output.
- Do not invent score rows. Scores should only come from a scoring workflow or known score export.
- If a required field is missing, choose a deterministic fallback and document it.

## Field Mapping Guidance

- `trace_id`: stable conversation/session ID. If missing, derive from source filename and record index.
- `session_id`: source session ID, usually the same as `trace_id`.
- `user_id`: stable user/account ID, or a deterministic placeholder such as `unknown_user_0001`.
- `domain`: broad source area, such as `support`, `sales`, `coding`, `research`, or `agent_logs`.
- `task_id`: task, topic, queue, issue type, or deterministic fallback.
- `outcome`: source outcome/status, or `unknown`.
- `reward`: numeric outcome if the source has one; otherwise `null`.
- `source_model`: assistant model name if known; otherwise `unknown_assistant`.
- `user_model`: `human`, simulator name, or `unknown_user`.
- `labels`: low-cardinality fields useful for filtering and segmenting.
- `metadata`: provenance, raw source labels, timestamps, and adapter-specific context.
- `turns`: ordered messages with `turn_id`, `index`, `role`, `content`, and optional `tool_name`, `reasoning`, `timestamp`.

## Pointing Persona Audit At The Data

Choose one path:

1. Normalized local file (preferred first run)
   - Write either a JSON array or JSONL file.
   - Run `uv run python -m backend.scripts.validate_traces <path>`.
   - Set `PERSONA_AUDIT_LOCAL_TRACES=<path>`.
   - Optionally set `PERSONA_AUDIT_LOCAL_PROVIDER_ID` and `PERSONA_AUDIT_LOCAL_LABEL`.
   - Open `http://localhost:5173/?provider=local`.

2. Source-specific adapter
   - Add loader code under `backend/adapters/<source>/`.
   - Return `list[AuditTrace]`, `provider_id`, and `source` text.
   - Register the provider in `backend/api/providers/` (one module with a SPEC + one registry entry; see docs/adapter-contract.md). Nothing else in the serving layer needs editing.
   - Configure `ProviderSpec.dimensions` for the dataset's segment/action/cohort fields.
   - Configure `character_reference_provider` only when a scientifically valid comparison corpus exists; otherwise Character uses a self profile.
   - Add focused loader/provider tests.

3. Postgres-compatible tables
   - Convert source records into rows compatible with `persona_audit_traces` and `persona_audit_turns`.
   - Use `PERSONA_AUDIT_DATABASE_URL` for the database DSN.
   - Keep `provider_id` stable and unique for the dataset.
   - Verify `/api/audit/report?provider=<provider>` before changing frontend code.

Private `turn.reasoning` text is discarded during Postgres upload by default.
Retain it only with `--persist-reasoning` or
`PERSONA_AUDIT_PERSIST_REASONING=1`; the upload summary warns and counts
discarded reasoning turns.

## Required Response From The Coding Agent

After conversion or adapter work, report:

- Source format inspected.
- Provider ID chosen.
- Files added or changed.
- Required-field fallbacks used.
- Any lossy mappings.
- How to run the app against the converted data.
- Verification commands run and their results.
