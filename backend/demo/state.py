"""Persistent hill-climb state under artifacts/demo_hillclimb/state.json."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from backend.paths import REPO_ROOT

HILLCLIMB_ROOT = REPO_ROOT / "artifacts" / "demo_hillclimb"
STATE_PATH = HILLCLIMB_ROOT / "state.json"


@dataclass
class HillClimbState:
    stage: int = 0
    iteration: int = 0
    # Active prompt ids per track; bump these when sharpening a persona.
    prompt_ids: dict[str, str] = field(
        default_factory=lambda: {"sol": "sol_v1", "marrow": "marrow_v1", "control": "control_v1"}
    )
    # True once Stage 2 passes: prompts must not change afterwards.
    frozen: bool = False
    best_objective: float | None = None
    best_iteration: int | None = None
    # Append-only log: one entry per iteration with prompts, run ids, QA and
    # separation outcomes, and freeform notes.
    history: list[dict[str, Any]] = field(default_factory=list)

    def record_iteration(self, entry: dict[str, Any]) -> None:
        entry = {"iteration": self.iteration, **entry}
        self.history = [
            existing
            for existing in self.history
            if int(existing.get("iteration", -1)) != self.iteration
        ]
        self.history.append(entry)
        self._refresh_best()

    def _refresh_best(self) -> None:
        self.best_objective = None
        self.best_iteration = None
        for entry in self.history:
            objective = entry.get("objective")
            if isinstance(objective, (int, float)) and (
                self.best_objective is None or objective > self.best_objective
            ):
                self.best_objective = float(objective)
                self.best_iteration = int(entry.get("iteration", 0))


def load_state(path: str | Path = STATE_PATH) -> HillClimbState:
    state_path = Path(path)
    if not state_path.exists():
        return HillClimbState()
    payload = json.loads(state_path.read_text(encoding="utf-8"))
    return HillClimbState(
        stage=int(payload.get("stage", 0)),
        iteration=int(payload.get("iteration", 0)),
        prompt_ids=dict(payload.get("prompt_ids", {})),
        frozen=bool(payload.get("frozen", False)),
        best_objective=payload.get("best_objective"),
        best_iteration=payload.get("best_iteration"),
        history=list(payload.get("history", [])),
    )


def save_state(state: HillClimbState, path: str | Path = STATE_PATH) -> None:
    state_path = Path(path)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(asdict(state), indent=2, sort_keys=True), encoding="utf-8")
