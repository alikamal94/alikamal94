"""Provisional supply/demand zones from H4 swing structure.

Used only when Ali hasn't set zones in gold_levels.md, or they are more than 14 days old.
The approval card always says the zones were auto-derived and unconfirmed; Ali confirms or replaces them.
"""
from __future__ import annotations

from datetime import date

from .data.prices import Candle
from .schemas import Zone

MAX_AGE_DAYS = 14


def pivots(candles: list[Candle], k: int = 2) -> tuple[list[float], list[float]]:
    """Fractal pivots: a high (low) higher (lower) than the k bars on each side."""
    highs, lows = [], []
    for i in range(k, len(candles) - k):
        window = candles[i - k:i + k + 1]
        c = candles[i]
        if all(c.high > w.high for w in window if w is not c):
            highs.append(c.high)
        if all(c.low < w.low for w in window if w is not c):
            lows.append(c.low)
    return highs, lows


def _cluster(prices: list[float], band_min: float, band_max: float) -> list[tuple[float, float, int]]:
    """Group nearby pivot prices into bands between band_min and band_max wide. Returns (low, high, touches)."""
    out: list[tuple[float, float, int]] = []
    group: list[float] = []
    for p in sorted(prices):
        if group and p - group[0] > band_max:
            out.append(_band(group, band_min, band_max))
            group = []
        group.append(p)
    if group:
        out.append(_band(group, band_min, band_max))
    return out


def _band(group: list[float], band_min: float, band_max: float) -> tuple[float, float, int]:
    lo, hi = min(group), max(group)
    mid = (lo + hi) / 2
    width = min(max(hi - lo, band_min), band_max)
    return round(mid - width / 2, 2), round(mid + width / 2, 2), len(group)


def derive_zones(candles: list[Candle], band_min: float = 15, band_max: float = 25, per_side: int = 1) -> list[Zone]:
    """Nearest supply band(s) above the last close and demand band(s) below it."""
    if len(candles) < 10:
        return []
    price = candles[-1].close
    highs, lows = pivots(candles)
    supply = [b for b in _cluster(highs, band_min, band_max) if b[0] > price]
    demand = [b for b in _cluster(lows, band_min, band_max) if b[1] < price]
    supply.sort(key=lambda b: b[0] - price)
    demand.sort(key=lambda b: price - b[1])
    return ([Zone(kind="supply", low=lo, high=hi) for lo, hi, _ in supply[:per_side]]
            + [Zone(kind="demand", low=lo, high=hi) for lo, hi, _ in demand[:per_side]])


def is_stale(updated: date | None, today: date) -> bool:
    return updated is None or (today - updated).days > MAX_AGE_DAYS
