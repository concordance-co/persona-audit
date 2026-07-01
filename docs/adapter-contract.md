# Adapter Contract

Persona Audit works on normalized conversation traces. A source adapter can read any system's data, but it should emit the same logical shape as `backend/api/models.py`.

## Trace Shape

One trace is one conversation or session.

```json
{
  "trace_id": "session_001",
  "session_id": "session_001",
  "user_id": "user_123",
  "domain": "support",
  "task_id": "refund_request",
  "outcome": "resolved",
  "reward": 1.0,
  "source_model": "assistant-model-name",
  "user_model": "human",
  "labels": {
    "segment": "billing"
  },
  "metadata": {
    "source": "my_adapter"
  },
  "turns": [
    {
      "turn_id": "turn_000",
      "index": 0,
      "role": "user",
      "content": "Can I get a refund?"
    },
    {
      "turn_id": "turn_001",
      "index": 1,
      "role": "assistant",
      "content": "I can help check the policy.",
      "reasoning": "optional private reasoning text",
      "timestamp": "2026-06-30T12:00:00Z"
    }
  ]
}
```

## Required Fields

Trace:

- `trace_id`
- `session_id`
- `user_id`
- `domain`
- `task_id`
- `outcome`
- `source_model`
- `user_model`
- `turns`

Turn:

- `turn_id`
- `index`
- `role`
- `content`

## Optional Fields

- `reward`: numeric outcome score if available.
- `labels`: source-specific tags used for segments and filters.
- `metadata`: source provenance and adapter-specific fields.
- `turn.tool_name`: tool call label.
- `turn.reasoning`: optional reasoning span for adapters that expose it.
- `turn.timestamp`: source timestamp.

## Adapter Rules

- Preserve source IDs when possible.
- Do not include secrets or credentials in labels or metadata.
- Keep private reasoning opt-in and documented.
- Emit assistant turns with enough text for scoring.
- Put source-specific parsing in `backend/adapters/<source>/`.
- Keep provider copy in `backend/api/provider.py`.
- Keep source selection in `backend/api/trace_source.py`.

## JSONL Conversion Target

For local conversion work, use one JSON object per line, with each object matching the trace shape above. The repo intentionally does not try to provide a universal importer for every source format. Instead, use this contract as the target shape for a small source-specific adapter or one-time conversion.

Recommended flow:

1. Inspect the source data and identify conversation boundaries, roles, stable IDs, timestamps, and metadata.
2. Convert each conversation/session into one normalized trace object.
3. Validate that each trace has the required fields listed above.
4. Choose how the app should read it:
   - Add a small source-specific loader under `backend/adapters/<source>/` and route it through `backend/api/trace_source.py`.
   - Or upload normalized trace/turn rows to the Postgres-compatible tables created by `backend/scripts/upload_local_data_to_neon.py`.
5. Keep scoring optional. Do not invent score rows when only raw conversations are available.

Use `docs/llm-data-conversion-instructions.md` as the coding-agent instruction template for source-specific conversion.

## Score Rows

Score rows are optional. Without score rows, the dashboard can still show basic sessions and source coverage. Trait/emotion baselines need rows with:

- `run_id`
- `score_family`
- `coordinate`
- `trace_id`
- `turn_index`
- `provider_id`
- `score`

The upload scripts use a wider canonical table shape from `backend/scripts/upload_tau2_scores_to_neon.py`.


## Postgres Trace Tables

The built-in upload helpers create two normalized trace tables by default:

- `behavior_audit_traces`
- `behavior_audit_turns`

The trace table stores one row per conversation, keyed by `(provider_id, trace_id)`. The turn table stores one row per message/tool turn, keyed by `(provider_id, trace_id, turn_index)`. See `backend/scripts/upload_local_data_to_neon.py` for the exact table columns.

Use a stable `provider_id` for each imported dataset, such as `acme_support_v1` or `my_agent_logs_v1`. The dashboard can then select that provider once it is wired through `backend/api/provider.py` and `backend/api/trace_source.py`.
