"""Trait "tells" surfaced for Hermes sessions.

The traits listed here are the z-scored assistant-axis coordinates the Hermes
overview highlights as behavioral tells (see ``backend/api/hermes.py``). A
fuller "thought vs. said" congruence analysis (scoring reasoning and response
sections separately and contrasting them) was prototyped here but never wired
into the product; see git history if you want to revive it.
"""

from __future__ import annotations

TELL_TRAITS = ("sycophantic", "manipulative", "condescending")
