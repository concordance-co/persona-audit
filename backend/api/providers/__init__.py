"""Registered data providers.

Adding a provider = one new module exposing a ``SPEC`` + one entry in the
tuple below. ``backend.api.registry`` documents the spec fields;
``persona_demo`` is the smallest worked example.
"""

from __future__ import annotations

from backend.api.providers import hermes, persona_demo, tau2
from backend.api.registry import ProviderSpec

REGISTRY: dict[str, ProviderSpec] = {spec.key: spec for spec in (tau2.SPEC, hermes.SPEC, persona_demo.SPEC)}
