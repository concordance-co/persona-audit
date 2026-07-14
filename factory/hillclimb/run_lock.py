"""Active-run lock for the demo hill-climb monitor.

The scheduled monitor may check in more often than one Modal iteration takes.
This lock makes "already running" a deterministic state so the monitor never
launches overlapping GPU work.
"""

from __future__ import annotations

import json
import os
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from factory.hillclimb.state import HILLCLIMB_ROOT

RUN_LOCK_PATH = HILLCLIMB_ROOT / "active_run.json"


def active_run(path: str | Path = RUN_LOCK_PATH) -> dict[str, Any] | None:
    lock_path = Path(path)
    if not lock_path.exists():
        return None
    try:
        payload = json.loads(lock_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"path": str(lock_path), "stale": True, "reason": "lock file is not valid JSON"}
    pid = payload.get("pid")
    if not isinstance(pid, int) or pid <= 0:
        return {**payload, "path": str(lock_path), "stale": True, "reason": "lock file has no valid pid"}
    if not _pid_is_running(pid):
        return {**payload, "path": str(lock_path), "stale": True, "reason": f"pid {pid} is not running"}
    return {**payload, "path": str(lock_path), "stale": False}


@contextmanager
def run_lock(metadata: Mapping[str, Any], path: str | Path = RUN_LOCK_PATH) -> Iterator[None]:
    lock_path = Path(path)
    current = active_run(lock_path)
    if current and not current.get("stale"):
        raise RuntimeError(
            f"demo hill-climb run already active (pid={current.get('pid')} command={current.get('command')!r})"
        )

    lock_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        **dict(metadata),
        "pid": os.getpid(),
        "started_at": datetime.now(UTC).isoformat(timespec="seconds"),
    }
    lock_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    try:
        yield
    finally:
        try:
            current_payload = json.loads(lock_path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            return
        if current_payload.get("pid") == os.getpid():
            lock_path.unlink()


def _pid_is_running(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True
