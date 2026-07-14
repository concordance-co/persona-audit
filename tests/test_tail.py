from __future__ import annotations

from backend.api.tail import compute_tail

A = "assistant_axis_trait__aa"
B = "assistant_axis_trait__bb"
HOSTILE = "assistant_axis_trait__hostile"
CALM = "assistant_axis_trait__calm"


def _row(coordinate: str, trace_id: str, score: float, turn_index: int = 0) -> dict:
    return {"coordinate": coordinate, "trace_id": trace_id, "score": score, "turn_index": turn_index}


def _two_mode_corpus() -> list[dict]:
    """200 quiet turns + two dense, well-separated extreme modes (aa-high, bb-high)."""
    rows: list[dict] = []
    for i in range(500):
        rows.append(_row(A, f"n{i}", (i % 5) * 0.05))
        rows.append(_row(B, f"n{i}", ((i + 2) % 5) * 0.05))
    for i in range(30):  # mode A: aa extreme, bb quiet
        rows.append(_row(A, f"a{i}", 5.0 + i * 0.02))
        rows.append(_row(B, f"a{i}", (i % 3) * 0.05))
    for i in range(30):  # mode B: bb extreme, aa quiet
        rows.append(_row(A, f"b{i}", (i % 3) * 0.05))
        rows.append(_row(B, f"b{i}", 5.0 + i * 0.02))
    return rows


def test_compute_tail_discovers_separated_modes() -> None:
    result = compute_tail(_two_mode_corpus())
    modes = result["modes"]
    assert len(modes) >= 2
    # Some mode is defined by aa-high and some by bb-high (the signature is signed,
    # so the *top* entry of a mode may instead be the suppressed opposite coordinate).
    aa_high = any(s["trait"] == "aa" and s["gap"] > 0 for m in modes for s in m["signature"])
    bb_high = any(s["trait"] == "bb" and s["gap"] > 0 for m in modes for s in m["signature"])
    assert aa_high and bb_high


def test_compute_tail_severity_size_and_exemplars() -> None:
    result = compute_tail(_two_mode_corpus())
    for mode in result["modes"]:
        assert mode["reach"] >= mode["central_severity"]  # p95 >= median
        assert 0 < mode["size_share"] <= 1
        assert mode["trace_count"] >= 1
        for key in ("representative", "worst"):
            assert mode[key]["trace_id"]
            assert mode[key]["peak_trait"] in {"aa", "bb"}


def test_compute_tail_meta_reports_tail_and_total() -> None:
    result = compute_tail(_two_mode_corpus())
    meta = result["meta"]
    assert meta["total_traces"] == 560  # 500 quiet + 30 + 30
    assert meta["n_tail_traces"] <= meta["total_traces"]
    assert meta["n_tail_turns"] >= 60  # at least the two modes' turns enter the tail


def test_compute_tail_ignores_non_persona_and_handles_sparse() -> None:
    # Non-persona coordinates are excluded; with no persona rows there are no modes.
    rows = [_row("emotion__calm", f"e{i}", float(i)) for i in range(50)]
    result = compute_tail(rows)
    assert result["modes"] == []
    assert result["meta"]["coordinates"] == []


def _concern_vs_benign_corpus() -> list[dict]:
    """Quiet background + a hostile (concern) mode and a calm (benign) mode."""
    rows: list[dict] = []
    for i in range(500):
        rows.append(_row(HOSTILE, f"n{i}", (i % 5) * 0.05))
        rows.append(_row(CALM, f"n{i}", ((i + 2) % 5) * 0.05))
    for i in range(30):  # hostile extreme -> concerning
        rows.append(_row(HOSTILE, f"h{i}", 5.0 + i * 0.02))
        rows.append(_row(CALM, f"h{i}", (i % 3) * 0.05))
    for i in range(30):  # calm extreme -> benign
        rows.append(_row(HOSTILE, f"c{i}", (i % 3) * 0.05))
        rows.append(_row(CALM, f"c{i}", 5.0 + i * 0.02))
    return rows


def test_compute_tail_flags_concern_and_clears_benign() -> None:
    result = compute_tail(_concern_vs_benign_corpus())
    by_peak = {m["representative"]["peak_trait"]: m for m in result["modes"]}
    assert "hostile" in by_peak and "calm" in by_peak
    hostile_mode = by_peak["hostile"]
    calm_mode = by_peak["calm"]
    assert hostile_mode["concerning"] is True
    assert any(c["trait"] == "hostile" for c in hostile_mode["concern_traits"])
    assert calm_mode["concerning"] is False
    assert calm_mode["concern_traits"] == []


def test_compute_tail_signature_is_signed() -> None:
    # A mode defined partly by a *suppressed* coordinate keeps the negative sign.
    result = compute_tail(_two_mode_corpus())
    # The aa-high mode: the one whose aa coordinate has the largest positive gap.
    aa_mode = max(
        result["modes"],
        key=lambda m: max([s["gap"] for s in m["signature"] if s["trait"] == "aa"], default=-9.0),
    )
    # In the aa-high mode, the opposite coordinate bb should read suppressed if it clears the cutoff.
    bb_entry = next((s for s in aa_mode["signature"] if s["trait"] == "bb"), None)
    if bb_entry is not None:
        assert bb_entry["gap"] < 0
