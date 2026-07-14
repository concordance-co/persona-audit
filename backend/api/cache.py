"""Registry of the serving layer's data caches, with one clear-all switch.

The report/score view-models memoize aggressively (the underlying data only
changes on upload or file swap). Every data-dependent cache registers here so
``POST /api/cache/clear`` can invalidate them all without a process restart.
Static metadata caches (e.g. emotion-cluster definitions) intentionally do not
register — they change only with code.
"""

from __future__ import annotations

from collections.abc import Callable
from functools import lru_cache
from typing import Any

_REGISTERED: list[Any] = []


def data_cache(maxsize: int = 4) -> Callable:
    """``functools.lru_cache`` that also registers for :func:`clear_all`."""

    def decorate(fn: Callable) -> Callable:
        cached = lru_cache(maxsize=maxsize)(fn)
        _REGISTERED.append(cached)
        return cached

    return decorate


def clear_all() -> int:
    """Clear every registered cache; returns how many were cleared."""

    for cached in _REGISTERED:
        cached.cache_clear()
    return len(_REGISTERED)
