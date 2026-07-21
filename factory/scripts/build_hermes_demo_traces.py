"""Build the bundled Hermes demo dataset from real hermes-agent trajectories.

Downloads a small deterministic sample of the Apache-2.0 Hugging Face dataset
``lambda/hermes-agent-reasoning-traces`` (multi-turn tool-calling agent
sessions with reasoning blocks) via the datasets-server rows API — no
``datasets``/``huggingface_hub`` dependency — and normalizes each trajectory
into the product's ``AuditTrace`` shape, mirroring the field mapping of the
live Hermes state.db adapter (backend/adapters/hermes/adapter.py).

    uv run python -m factory.scripts.build_hermes_demo_traces

Emits data/hermes_demo/normalized_traces.json (the hermes provider's bundled
fallback) plus a manifest recording the sampled row ids for reproducibility.
Trace ids are derived from the immutable HF row ids, so re-running the script
against the same rows yields the same ids — required for the shipped score
cache (data/supplemental_scores/) to keep joining.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import urllib.parse
import urllib.request
from collections.abc import Iterator
from typing import Any

from backend.api.models import AuditTrace, AuditTurn
from backend.api.trace_io import save_traces
from backend.paths import REPO_ROOT

DATASET = "lambda/hermes-agent-reasoning-traces"
ROWS_API = "https://datasets-server.huggingface.co/rows"
OUT_DIR = REPO_ROOT / "data" / "hermes_demo"

THINK_RE = re.compile(r"<think>(.*?)</think>", re.DOTALL)
TOOL_CALL_RE = re.compile(r"<tool_call>(.*?)</tool_call>", re.DOTALL)
TOOL_RESPONSE_RE = re.compile(r"<tool_response>(.*?)</tool_response>", re.DOTALL)

ROLE_BY_SOURCE = {"human": "user", "gpt": "assistant", "tool": "tool"}

# Keep the shipped file and the demo scoring run small: skip giant sessions
# (chars measured without the boilerplate system prompt, which is dropped).
MAX_TRACE_CHARS = 60_000
MAX_TURNS = 40


def fetch_rows(config: str, offset: int, length: int) -> list[dict[str, Any]]:
    query = urllib.parse.urlencode(
        {"dataset": DATASET, "config": config, "split": "train", "offset": offset, "length": length}
    )
    with urllib.request.urlopen(f"{ROWS_API}?{query}", timeout=60) as response:
        payload = json.load(response)
    return [entry["row"] for entry in payload.get("rows", [])]


def _first_json_field(blocks: list[str], field: str) -> str | None:
    for block in blocks:
        try:
            data = json.loads(block.strip())
        except (json.JSONDecodeError, ValueError):
            continue
        value = data.get(field)
        if value:
            return str(value)
    return None


def _assistant_turn(value: str, index: int) -> AuditTurn:
    thinks = THINK_RE.findall(value)
    tool_calls = TOOL_CALL_RE.findall(value)
    content = THINK_RE.sub("", value)
    content = TOOL_CALL_RE.sub("", content).strip()
    return AuditTurn(
        turn_id=f"turn_{index:04d}",
        role="assistant",
        content=content,
        index=index,
        tool_name=_first_json_field(tool_calls, "name"),
        reasoning="\n\n".join(block.strip() for block in thinks) or None,
    )


def _tool_turn(value: str, index: int) -> AuditTurn:
    responses = TOOL_RESPONSE_RE.findall(value)
    content = "\n".join(block.strip() for block in responses) if responses else value.strip()
    return AuditTurn(
        turn_id=f"turn_{index:04d}",
        role="tool",
        content=content,
        index=index,
        tool_name=_first_json_field(responses, "name"),
    )


def normalize_row(row: dict[str, Any], config: str) -> AuditTrace | None:
    conversations = [turn for turn in row.get("conversations", []) if turn.get("from") != "system"]
    if sum(len(str(turn.get("value") or "")) for turn in conversations) > MAX_TRACE_CHARS:
        return None
    if len(conversations) > MAX_TURNS:
        return None

    turns: list[AuditTurn] = []
    for index, turn in enumerate(conversations):
        role = ROLE_BY_SOURCE.get(str(turn.get("from")))
        value = str(turn.get("value") or "")
        if role is None or not value.strip():
            continue
        if role == "assistant":
            turns.append(_assistant_turn(value, index))
        elif role == "tool":
            turns.append(_tool_turn(value, index))
        else:
            turns.append(AuditTurn(turn_id=f"turn_{index:04d}", role="user", content=value.strip(), index=index))

    if not any(turn.role == "assistant" and turn.content for turn in turns):
        return None

    row_id = str(row["id"])
    trace_id = f"hermes_demo_{hashlib.sha1(row_id.encode()).hexdigest()[:12]}"
    category = str(row.get("category") or "hermes")
    subcategory = str(row.get("subcategory") or "general")
    task = " ".join(str(row.get("task") or "").split())
    title = task if len(task) <= 72 else task[:71] + "..."
    return AuditTrace(
        trace_id=trace_id,
        session_id=trace_id,
        user_id=_slug(subcategory),
        domain=category,
        task_id=title or trace_id,
        outcome="completed",
        reward=None,
        source_model=f"hermes-agent ({config})",
        user_model="hermes_user",
        turns=tuple(turns),
        labels={
            "provider": "hermes",
            "has_reasoning": any(bool(turn.reasoning) for turn in turns),
            "category": category,
            "subcategory": subcategory,
        },
        metadata={
            "source": category,
            "workflow": _slug(subcategory),
            "final_action": "completed",
            "title": title,
            "hermes_source": category,
            "hf_dataset": DATASET,
            "hf_row_id": row_id,
        },
    )


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_") or "general"


def iter_candidates(config: str, offset: int, scan: int) -> Iterator[dict[str, Any]]:
    page = 100
    for start in range(offset, offset + scan, page):
        rows = fetch_rows(config, start, min(page, offset + scan - start))
        if not rows:
            return
        yield from rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="kimi", help="HF dataset config (kimi or glm-5.1)")
    parser.add_argument("--count", type=int, default=30, help="Traces to keep")
    parser.add_argument("--offset", type=int, default=0, help="First dataset row to scan")
    parser.add_argument("--scan", type=int, default=300, help="How many rows to scan for candidates")
    args = parser.parse_args()

    traces: list[AuditTrace] = []
    scanned = 0
    for row in iter_candidates(args.config, args.offset, args.scan):
        scanned += 1
        trace = normalize_row(row, args.config)
        if trace is not None:
            traces.append(trace)
        if len(traces) >= args.count:
            break

    if len(traces) < args.count:
        print(f"warning: only {len(traces)} of {args.count} requested traces passed the size filters")
    if not traces:
        return 1

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / "normalized_traces.json"
    save_traces(traces, out_path)
    manifest = {
        "dataset": DATASET,
        "config": args.config,
        "offset": args.offset,
        "rows_scanned": scanned,
        "trace_count": len(traces),
        "max_trace_chars": MAX_TRACE_CHARS,
        "max_turns": MAX_TURNS,
        "rows": [{"trace_id": trace.trace_id, "hf_row_id": trace.metadata["hf_row_id"]} for trace in traces],
    }
    (OUT_DIR / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    turn_count = sum(len(trace.turns) for trace in traces)
    print(f"wrote {len(traces)} traces ({turn_count} turns) -> {out_path}")
    print(f"manifest -> {OUT_DIR / 'manifest.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
