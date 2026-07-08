"""Render the hill-climb monitoring dashboard as a self-contained HTML page.

Pure presentation: the driver gathers the loop's JSON artifacts and hands them
in; this module returns one HTML document with everything inlined (no server,
no external assets). The page meta-refreshes, and the driver regenerates it on
every tick, so opening ``artifacts/demo_hillclimb/report.html`` in a browser
is the whole monitoring UI.
"""

from __future__ import annotations

import html
import json
from typing import Any, Mapping, Sequence

REFRESH_SECONDS = 60

_DECISION_STATUS = {
    "DONE": ("good", "&#10003;", "complete: dataset frozen and saved"),
    "RUN_ITERATION": ("good", "&#9654;", "running mechanically"),
    "FINISH_ITERATION": ("good", "&#9654;", "finishing pipeline tail"),
    "WAIT_RUNNING": ("warning", "&#8987;", "iteration in progress"),
    "ESCALATE_PROMPT": ("serious", "&#9998;", "prompt revision needed"),
    "HOLD_HUMAN": ("warning", "&#9995;", "waiting on human curation"),
}

_CSS = """
:root {
  --surface-1: #fcfcfb; --page: #f9f9f7;
  --ink: #0b0b0b; --ink-2: #52514e; --muted: #898781;
  --grid: #e1e0d9; --baseline: #c3c2b7; --border: rgba(11,11,11,0.10);
  --pos: #2a78d6; --neg: #e34948;
  --good: #0ca30c; --warning: #fab219; --serious: #ec835a; --critical: #d03b3b;
  --good-text: #006300;
}
@media (prefers-color-scheme: dark) {
  :root {
    --surface-1: #1a1a19; --page: #0d0d0d;
    --ink: #ffffff; --ink-2: #c3c2b7; --muted: #898781;
    --grid: #2c2c2a; --baseline: #383835; --border: rgba(255,255,255,0.10);
    --pos: #3987e5; --neg: #e66767;
    --good-text: #0ca30c;
  }
}
* { box-sizing: border-box; }
body {
  margin: 0; padding: 24px; background: var(--page); color: var(--ink);
  font-family: system-ui, -apple-system, "Segoe UI", sans-serif; font-size: 14px;
}
h1 { font-size: 18px; margin: 0 0 4px; }
h2 { font-size: 13px; font-weight: 600; color: var(--ink-2); margin: 0 0 10px;
     text-transform: uppercase; letter-spacing: 0.04em; }
.sub { color: var(--muted); margin-bottom: 20px; }
.grid { display: grid; gap: 16px; grid-template-columns: repeat(auto-fit, minmax(340px, 1fr)); }
.card { background: var(--surface-1); border: 1px solid var(--border);
        border-radius: 8px; padding: 16px; }
.card.wide { grid-column: 1 / -1; }
.tiles { display: grid; gap: 16px; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
         margin-bottom: 16px; }
.tile { background: var(--surface-1); border: 1px solid var(--border);
        border-radius: 8px; padding: 14px 16px; }
.tile .label { color: var(--muted); font-size: 12px; margin-bottom: 4px; }
.tile .value { font-size: 26px; font-weight: 650; }
.tile .hint { color: var(--ink-2); font-size: 12px; margin-top: 2px; }
.status { display: inline-flex; align-items: center; gap: 6px; font-weight: 600; }
.status .dot { width: 9px; height: 9px; border-radius: 50%; display: inline-block; }
table { border-collapse: collapse; width: 100%; }
th { text-align: left; color: var(--muted); font-weight: 500; font-size: 12px;
     border-bottom: 1px solid var(--grid); padding: 4px 8px; }
td { padding: 5px 8px; border-bottom: 1px solid var(--grid);
     font-variant-numeric: tabular-nums; }
tr:last-child td { border-bottom: none; }
tr:hover td { background: color-mix(in srgb, var(--grid) 40%, transparent); }
.pass { color: var(--good-text); font-weight: 600; }
.fail { color: var(--critical); font-weight: 600; }
.chip { display: inline-block; padding: 1px 8px; border: 1px solid var(--border);
        border-radius: 10px; margin: 2px; color: var(--ink-2); font-size: 12px; }
pre { background: var(--surface-1); border: 1px solid var(--border); border-radius: 8px;
      padding: 12px; overflow-x: auto; font-size: 12px; color: var(--ink-2);
      max-height: 320px; overflow-y: auto; }
svg text { font-family: inherit; }
.axis-label { fill: var(--muted); font-size: 11px; }
.reason { color: var(--ink-2); line-height: 1.45; }
svg .bar:hover, svg .pt:hover { opacity: 0.8; }
"""


def _esc(value: Any) -> str:
    return html.escape(str(value))


def _surface_label(surface: str) -> str:
    parts = str(surface).split(".")
    core = parts[-2] if len(parts) >= 2 else parts[-1]
    return core.replace("__", ": ").replace("_", " ")


def _status_chip(action: str) -> str:
    role, icon, hint = _DECISION_STATUS.get(action, ("critical", "?", "unknown"))
    return (
        f'<span class="status"><span class="dot" style="background:var(--{role})"></span>'
        f"{icon}&nbsp;{_esc(action)}</span>"
        f'<div class="hint">{_esc(hint)}</div>'
    )


def _trend_svg(history: Sequence[Mapping[str, Any]], gate: float) -> str:
    points = [
        (int(entry["iteration"]), float(entry["objective"]))
        for entry in history
        if entry.get("objective") is not None
    ]
    if not points:
        return '<div class="sub">No evaluated iterations yet.</div>'
    width, height, pad = 560, 170, 34
    xs = [p[0] for p in points]
    ys = [p[1] for p in points] + [gate, 0.0]
    x_min, x_max = min(xs), max(xs)
    y_min, y_max = min(ys), max(ys)
    y_span = (y_max - y_min) or 1.0
    x_span = (x_max - x_min) or 1

    def sx(x: float) -> float:
        return pad + (x - x_min) / x_span * (width - 2 * pad)

    def sy(y: float) -> float:
        return height - pad - (y - y_min) / y_span * (height - 2 * pad)

    path = " ".join(
        f"{'M' if i == 0 else 'L'}{sx(x):.1f},{sy(y):.1f}" for i, (x, y) in enumerate(points)
    )
    dots = "".join(
        f'<circle class="pt" cx="{sx(x):.1f}" cy="{sy(y):.1f}" r="4" fill="var(--pos)">'
        f"<title>iteration {x}: objective {y:.3f}</title></circle>"
        for x, y in points
    )
    last_x, last_y = points[-1]
    return f"""<svg viewBox="0 0 {width} {height}" role="img" aria-label="Objective per iteration">
  <line x1="{pad}" y1="{sy(0):.1f}" x2="{width - pad}" y2="{sy(0):.1f}" stroke="var(--baseline)" stroke-width="1"/>
  <line x1="{pad}" y1="{sy(gate):.1f}" x2="{width - pad}" y2="{sy(gate):.1f}" stroke="var(--grid)" stroke-width="1" stroke-dasharray="4 3"/>
  <text class="axis-label" x="{width - pad}" y="{sy(gate) - 5:.1f}" text-anchor="end">gate {gate:g}</text>
  <path d="{path}" fill="none" stroke="var(--pos)" stroke-width="2"/>
  {dots}
  <text class="axis-label" x="{sx(last_x):.1f}" y="{sy(last_y) - 10:.1f}" text-anchor="middle" fill="var(--ink)">{last_y:.2f}</text>
  {"".join(f'<text class="axis-label" x="{sx(x):.1f}" y="{height - 12}" text-anchor="middle">#{x}</text>' for x in sorted(set(xs)))}
</svg>"""


def _surface_bars_svg(separation: Mapping[str, Any]) -> str:
    per_surface = separation.get("per_surface") or {}
    top = [s for s in separation.get("top_surfaces") or [] if s in per_surface]
    if not top:
        return '<div class="sub">No separation report yet.</div>'
    width, row_h, label_w, val_w = 560, 26, 190, 46
    height = row_h * len(top) + 20
    d_max = max(abs(float(per_surface[s]["d_sol_marrow"])) for s in top) or 1.0
    plot_w = width - label_w - val_w
    cx = label_w + plot_w / 2
    rows = []
    for i, surface in enumerate(top):
        d = float(per_surface[surface]["d_sol_marrow"])
        y = i * row_h + 8
        bar_len = abs(d) / d_max * (plot_w / 2 - 6)
        color = "var(--pos)" if d >= 0 else "var(--neg)"
        x = cx if d >= 0 else cx - bar_len
        # 4px rounded outer end, flat at the center baseline.
        rx = 4 if bar_len > 4 else 0
        rows.append(
            f'<rect class="bar" x="{x:.1f}" y="{y}" width="{bar_len:.1f}" height="12" rx="{rx}" fill="{color}">'
            f"<title>{_esc(_surface_label(surface))}: d = {d:+.2f}</title></rect>"
            f'<text class="axis-label" x="{label_w - 8}" y="{y + 10}" text-anchor="end" fill="var(--ink-2)">{_esc(_surface_label(surface))}</text>'
            f'<text class="axis-label" x="{(x + bar_len + 6) if d >= 0 else (x - 6):.1f}" y="{y + 10}"'
            f' text-anchor="{"start" if d >= 0 else "end"}" fill="var(--ink)">{d:+.2f}</text>'
        )
    legend_y = height - 4
    return f"""<svg viewBox="0 0 {width} {height}" role="img" aria-label="Top surfaces by paired effect size">
  <line x1="{cx}" y1="0" x2="{cx}" y2="{height - 18}" stroke="var(--baseline)" stroke-width="1"/>
  {"".join(rows)}
  <circle cx="{cx + 14}" cy="{legend_y - 4}" r="4" fill="var(--pos)"/>
  <text class="axis-label" x="{cx + 22}" y="{legend_y}">sol higher</text>
  <circle cx="{cx - 84}" cy="{legend_y - 4}" r="4" fill="var(--neg)"/>
  <text class="axis-label" x="{cx - 76}" y="{legend_y}">marrow higher</text>
</svg>"""


def _qa_table(qa: Mapping[str, Any] | None) -> str:
    if not qa:
        return '<div class="sub">No QA report yet.</div>'
    rows = []
    for check in qa.get("checks", ()):  # name/track/passed/value
        value = check.get("value")
        if isinstance(value, list):
            shown = "; ".join(str(v) for v in value[:3]) + (" ..." if len(value) > 3 else "")
            shown = shown or "none"
        elif isinstance(value, float):
            shown = f"{value:.2f}"
        else:
            shown = str(value)
        state = '<span class="pass">pass</span>' if check.get("passed") else '<span class="fail">FAIL</span>'
        rows.append(
            f"<tr><td>{_esc(check.get('name'))}</td><td>{_esc(check.get('track'))}</td>"
            f"<td>{_esc(shown)}</td><td>{state}</td></tr>"
        )
    return (
        "<table><thead><tr><th>check</th><th>track</th><th>value</th><th></th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>"
    )


def _history_table(history: Sequence[Mapping[str, Any]]) -> str:
    if not history:
        return '<div class="sub">No iterations recorded yet.</div>'
    rows = []
    for entry in reversed(list(history)[-10:]):
        objective = entry.get("objective")
        objective_cell = f"{objective:.3f}" if isinstance(objective, (int, float)) else "-"
        prompts = entry.get("prompt_ids") or {}
        sep_cell = '<span class="pass">pass</span>' if entry.get("separation_passed") else '<span class="fail">fail</span>'
        qa_cell = '<span class="pass">pass</span>' if entry.get("qa_passed") else '<span class="fail">fail</span>'
        rows.append(
            f"<tr><td>#{_esc(entry.get('iteration'))}</td><td>{_esc(entry.get('stage'))}</td>"
            f"<td>{objective_cell}</td><td>{sep_cell}</td><td>{qa_cell}</td>"
            f"<td>{_esc(' '.join(sorted(str(v) for v in prompts.values())))}</td></tr>"
        )
    return (
        "<table><thead><tr><th>iter</th><th>stage</th><th>objective</th>"
        "<th>separation</th><th>QA</th><th>prompts</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>"
    )


def render(
    *,
    state: Mapping[str, Any],
    decision: Mapping[str, Any],
    qa: Mapping[str, Any] | None,
    separation: Mapping[str, Any] | None,
    active_run: Mapping[str, Any] | None,
    escalation: Mapping[str, Any] | None,
    log_tail: str,
    generated_at: str,
) -> str:
    history = list(state.get("history") or [])
    last = history[-1] if history else {}
    objective = last.get("objective")
    gates = (separation or {}).get("gates") or {}
    gate = float(gates.get("min_objective_d", 0.8))
    confounded = (separation or {}).get("confounded_surfaces") or []
    reasons = (separation or {}).get("reasons") or []

    # A frozen state is success, not a block: show it as DONE, not "needs human".
    frozen = bool(state.get("frozen"))
    display_action = "DONE" if frozen else str(decision.get("action"))

    done_banner = ""
    if frozen:
        done_banner = (
            '<div class="card wide" style="border-color:var(--good)">'
            '<h2 style="color:var(--good)">&#10003; Complete</h2>'
            '<div class="reason">The hill climb is finished. Prompts are frozen and the demo '
            "dataset is saved under <code>data/demo/stage2/</code>. The loop intentionally "
            "stops here; nothing further is required.</div></div>"
        )

    run_panel = ""
    if active_run:
        run_panel = (
            '<div class="card wide"><h2>Active run</h2><div class="reason">'
            f"pid {_esc(active_run.get('pid'))} &middot; {_esc(active_run.get('command'))} "
            f"&middot; started {_esc(active_run.get('started_at'))}"
            + (" &middot; <span class=fail>STALE</span>" if active_run.get("stale") else "")
            + "</div></div>"
        )
    escalation_panel = ""
    if escalation:
        escalation_panel = (
            '<div class="card"><h2>Last escalation</h2><div class="reason">'
            f"iteration {_esc(escalation.get('iteration'))} at {_esc(escalation.get('started_at'))}<br>"
            f"{_esc(escalation.get('reason'))}</div></div>"
        )

    prompts = state.get("prompt_ids") or {}
    prompt_chips = "".join(f'<span class="chip">{_esc(t)}: {_esc(p)}</span>' for t, p in sorted(prompts.items()))
    confound_chips = (
        "".join(f'<span class="chip">{_esc(_surface_label(s))}</span>' for s in confounded)
        or '<span class="sub">none flagged</span>'
    )
    reason_list = "".join(f"<li>{_esc(r)}</li>" for r in reasons)
    gates_panel = (
        f"<ul class='reason'>{reason_list}</ul>" if reasons else '<div class="pass">all gates passing</div>'
    )

    objective_text = f"{objective:.2f}" if isinstance(objective, (int, float)) else "-"
    best = state.get("best_objective")
    best_text = f"{best:.2f} (iter {state.get('best_iteration')})" if isinstance(best, (int, float)) else "-"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta http-equiv="refresh" content="{REFRESH_SECONDS}">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Demo Hill-Climb</title>
<style>{_CSS}</style>
</head>
<body>
<h1>Demo Hill-Climb</h1>
<div class="sub">generated {_esc(generated_at)} &middot; auto-refreshes every {REFRESH_SECONDS}s &middot; regenerated on every tick</div>

<div class="tiles">
  <div class="tile"><div class="label">Stage</div><div class="value">{_esc(state.get("stage"))}</div>
    <div class="hint">iteration {_esc(state.get("iteration"))}{" &middot; FROZEN" if state.get("frozen") else ""}</div></div>
  <div class="tile"><div class="label">Objective</div><div class="value">{objective_text}</div>
    <div class="hint">best {best_text}</div></div>
  <div class="tile"><div class="label">Separation</div>
    <div class="value">{'<span class="pass">pass</span>' if last.get("separation_passed") else '<span class="fail">fail</span>'}</div>
    <div class="hint">gate: mean |d| &ge; {gate:g}</div></div>
  <div class="tile"><div class="label">Transcript QA</div>
    <div class="value">{'<span class="pass">pass</span>' if last.get("qa_passed") else '<span class="fail">fail</span>'}</div>
    <div class="hint">{_esc(", ".join((qa or {}).get("failing_tracks") or []) or "all tracks clean")}</div></div>
  <div class="tile"><div class="label">Decision</div><div class="value" style="font-size:15px">{_status_chip(display_action)}</div></div>
</div>

{done_banner}

{run_panel}

<div class="grid">
  <div class="card"><h2>Objective per iteration</h2>{_trend_svg(history, gate)}</div>
  <div class="card"><h2>Top surfaces &middot; paired d (sol vs marrow)</h2>{_surface_bars_svg(separation or {})}</div>
  <div class="card"><h2>Current decision</h2>
    <div class="reason">{_esc(decision.get("reason"))}</div>
    {f'<pre style="max-height:none">{_esc(decision.get("command"))}</pre>' if decision.get("command") else ""}
  </div>
  <div class="card"><h2>Gates</h2>{gates_panel}
    <h2 style="margin-top:14px">Prompts</h2>{prompt_chips}
    <h2 style="margin-top:14px">Length-confounded (excluded)</h2>{confound_chips}</div>
  {escalation_panel}
  <div class="card wide"><h2>Transcript QA checks</h2>{_qa_table(qa)}</div>
  <div class="card wide"><h2>Iteration history</h2>{_history_table(history)}</div>
  <div class="card wide"><h2>Tick log (tail)</h2><pre>{_esc(log_tail or "(empty)")}</pre></div>
</div>
</body>
</html>"""


def state_to_dict(state: Any) -> dict[str, Any]:
    """Adapt HillClimbState to the plain mapping render() expects."""

    return {
        "stage": state.stage,
        "iteration": state.iteration,
        "prompt_ids": dict(state.prompt_ids),
        "frozen": state.frozen,
        "best_objective": state.best_objective,
        "best_iteration": state.best_iteration,
        "history": [dict(entry) for entry in state.history],
    }


if __name__ == "__main__":  # pragma: no cover - manual preview helper
    print(json.dumps({"module": "backend.demo.report_html", "refresh": REFRESH_SECONDS}))
