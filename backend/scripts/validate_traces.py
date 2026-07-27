"""Validate normalized Persona Audit JSON or JSONL before registering/uploading it."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from backend.api.trace_io import TraceValidationError, load_traces


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path)
    args = parser.parse_args()

    try:
        traces = load_traces(args.path)
    except (OSError, TraceValidationError) as exc:
        parser.error(str(exc))

    turns = [turn for trace in traces for turn in trace.turns]
    summary = {
        "path": str(args.path),
        "trace_count": len(traces),
        "turn_count": len(turns),
        "assistant_turn_count": sum(turn.role == "assistant" for turn in turns),
        "reasoning_turn_count": sum(bool(turn.reasoning) for turn in turns),
        "status": "valid",
    }
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
