"""Tauro-style candlestick chart as inline SVG (red down candles, white up candles, labelled zones).

Drawn in code from the price feed so every number on the chart is exact.
SVG text is shaped by Chromium at render time, so Arabic zone labels come out correct.
"""
from __future__ import annotations

from html import escape

from ..data.prices import Candle
from ..schemas import Zone

RED = "#FE0000"
WHITE = "#FFFFFF"
GREY = "#B3B3B3"
PANEL = "#1A1A1A"

ZONE_LABEL = {"supply": "منطقة عرض", "demand": "منطقة طلب"}


def _fmt(p: float) -> str:
    return f"{p:,.2f}" if p >= 100 else f"{p:.5f}".rstrip("0")


def candle_svg(candles: list[Candle], zones: list[Zone], width: int, height: int) -> str:
    if not candles:
        raise ValueError("no candles to draw")
    axis_w = 150
    pad_t, pad_b = 24, 24
    plot_w = width - axis_w
    lows = [c.low for c in candles] + [z.low for z in zones]
    highs = [c.high for c in candles] + [z.high for z in zones]
    lo, hi = min(lows), max(highs)
    span = hi - lo or 1
    lo, hi = lo - span * 0.12, hi + span * 0.12

    def y(p: float) -> float:
        return pad_t + (hi - p) / (hi - lo) * (height - pad_t - pad_b)

    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
             f'viewBox="0 0 {width} {height}" font-family="Cairo" direction="ltr">']

    # Grid + price axis (5 lines)
    last_y = y(candles[-1].close)
    for i in range(5):
        p = lo + (hi - lo) * (i + 0.5) / 5
        yy = y(p)
        if abs(yy - last_y) < 44:
            continue
        parts.append(f'<line x1="0" y1="{yy:.1f}" x2="{plot_w}" y2="{yy:.1f}" stroke="#2A2A2A" stroke-width="1"/>')
        parts.append(f'<text x="{plot_w + 16}" y="{yy + 9:.1f}" fill="{GREY}" font-size="26">{_fmt(p)}</text>')

    # Zones behind the candles; their labels go on top at the end
    labels: list[str] = []
    for z in zones:
        color = RED if z.kind == "supply" else WHITE
        y1, y2 = y(z.high), y(z.low)
        label = escape(z.label or ZONE_LABEL[z.kind])
        parts.append(f'<rect x="0" y="{y1:.1f}" width="{plot_w}" height="{max(y2 - y1, 4):.1f}" '
                     f'fill="{color}" fill-opacity="0.14" stroke="{color}" stroke-opacity="0.6" stroke-width="2"/>')
        # Range on the left, Arabic label on the right: two separate texts so bidi never mixes them.
        ty = y1 - 12 if z.kind == "supply" else y2 + 34
        halo = f'paint-order="stroke" stroke="{PANEL}" stroke-width="8" stroke-linejoin="round"'
        labels.append(f'<text x="14" y="{ty:.1f}" fill="{color}" font-size="26" font-weight="700" '
                     f'direction="ltr" {halo}>{_fmt(z.low)} – {_fmt(z.high)}</text>')
        labels.append(f'<text x="{plot_w - 14}" y="{ty:.1f}" fill="{color}" font-size="26" font-weight="700" '
                     f'text-anchor="end" {halo}>{label}</text>')

    # Candles
    n = len(candles)
    slot = plot_w / n
    body_w = max(slot * 0.62, 2)
    for i, c in enumerate(candles):
        cx = i * slot + slot / 2
        up = c.close >= c.open
        color = WHITE if up else RED
        top, bot = y(max(c.open, c.close)), y(min(c.open, c.close))
        parts.append(f'<line x1="{cx:.1f}" y1="{y(c.high):.1f}" x2="{cx:.1f}" y2="{y(c.low):.1f}" '
                     f'stroke="{color}" stroke-width="2"/>')
        parts.append(f'<rect x="{cx - body_w / 2:.1f}" y="{top:.1f}" width="{body_w:.1f}" '
                     f'height="{max(bot - top, 1.5):.1f}" fill="{color}"/>')

    # Last price tag
    last = candles[-1].close
    ly = y(last)
    parts.append(f'<line x1="0" y1="{ly:.1f}" x2="{plot_w}" y2="{ly:.1f}" stroke="{WHITE}" '
                 f'stroke-dasharray="6 6" stroke-opacity="0.5"/>')
    parts.append(f'<rect x="{plot_w + 4}" y="{ly - 20:.1f}" width="{axis_w - 8}" height="40" rx="6" fill="{RED}"/>')
    parts.append(f'<text x="{plot_w + 16}" y="{ly + 10:.1f}" fill="{WHITE}" font-size="26" font-weight="700">'
                 f'{_fmt(last)}</text>')
    parts.extend(labels)
    parts.append("</svg>")
    return "".join(parts)
