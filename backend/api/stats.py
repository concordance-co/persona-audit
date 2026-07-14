"""Shared numeric helpers for Persona Audit view models."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Any


def as_float(value: Any) -> float | None:
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


def avg(values: Sequence[Any]) -> float | None:
    numbers = [as_float(value) for value in values]
    numbers = [value for value in numbers if value is not None]
    return round(sum(numbers) / len(numbers), 4) if numbers else None


def mean(values: Sequence[float]) -> float | None:
    return sum(values) / len(values) if values else None


def rms(values: Iterable[float]) -> float | None:
    numeric = [float(value) for value in values if value is not None]
    if not numeric:
        return None
    return (sum(value * value for value in numeric) / len(numeric)) ** 0.5


def stddev(values: Sequence[float]) -> float:
    if len(values) < 2:
        return 0.0
    mean_value = mean(values) or 0.0
    return (sum((value - mean_value) ** 2 for value in values) / (len(values) - 1)) ** 0.5


def quantile(sorted_values: Sequence[float], q: float) -> float:
    if not sorted_values:
        return 0.0
    if len(sorted_values) == 1:
        return sorted_values[0]
    position = (len(sorted_values) - 1) * q
    lower = int(position)
    upper = min(lower + 1, len(sorted_values) - 1)
    weight = position - lower
    return sorted_values[lower] * (1 - weight) + sorted_values[upper] * weight


def cohen_d(a: Sequence[float], b: Sequence[float]) -> float | None:
    if len(a) < 2 or len(b) < 2:
        return None
    sd_a = stddev(a)
    sd_b = stddev(b)
    pooled = (((len(a) - 1) * sd_a**2 + (len(b) - 1) * sd_b**2) / (len(a) + len(b) - 2)) ** 0.5
    if pooled == 0:
        return None
    return ((mean(a) or 0.0) - (mean(b) or 0.0)) / pooled


def histogram(values: Sequence[float], n_bins: int = 8) -> list[dict[str, Any]]:
    numeric = [float(value) for value in values]
    if not numeric:
        return []
    lo = min(numeric)
    hi = max(numeric)
    if lo == hi:
        return [{"bin_start": lo, "bin_end": hi, "count": len(numeric)}]
    step = (hi - lo) / n_bins
    counts = [0] * n_bins
    for value in numeric:
        idx = int((value - lo) / step)
        if idx == n_bins:
            idx = n_bins - 1
        counts[idx] += 1
    return [
        {"bin_start": round(lo + i * step, 4), "bin_end": round(lo + (i + 1) * step, 4), "count": counts[i]}
        for i in range(n_bins)
    ]


def histogram_counts(values: Sequence[float], lo: float, hi: float, n_bins: int) -> list[int]:
    """Fixed-range histogram: bin ``values`` into ``n_bins`` buckets spanning [lo, hi].

    Unlike :func:`histogram` (auto-ranged, dict rows), this keeps the caller's
    range and returns raw counts — used for aligned per-trait distributions.
    """

    if n_bins <= 0:
        return []
    if hi <= lo:
        hi = lo + 1.0
    width = (hi - lo) / n_bins
    counts = [0] * n_bins
    for value in values:
        index = int((value - lo) / width)
        if index >= n_bins:
            index = n_bins - 1
        elif index < 0:
            index = 0
        counts[index] += 1
    return counts


def pearson(xs: Sequence[float], ys: Sequence[float], *, ndigits: int | None = 4) -> float | None:
    n = len(xs)
    if n < 2 or n != len(ys):
        return None
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    numerator = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    dx2 = sum((x - mean_x) ** 2 for x in xs)
    dy2 = sum((y - mean_y) ** 2 for y in ys)
    denominator = (dx2 * dy2) ** 0.5
    if denominator == 0:
        return None
    value = numerator / denominator
    return round(value, ndigits) if ndigits is not None else value
