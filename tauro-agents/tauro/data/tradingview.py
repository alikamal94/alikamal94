"""TradingView price source: talks to the same TradingView connector (MCP server) the Claude app uses on Ali's Mac.

Set TAURO_PRICE_PROVIDER=tradingview and TAURO_TV_MCP_COMMAND to the command that starts that connector
(copy it from the Claude app's MCP settings, e.g. `node /path/to/tradingview-mcp/index.js`).

Read-only on Ali's chart: it switches the timeframe to pull bars, then restores the original one.
It never draws, never clears drawings, and never takes screenshots.
Untested against the live connector: tool names come from the gold-posts skill; the bar parser accepts the common shapes.
"""
from __future__ import annotations

import asyncio
import json
import os
import shlex
from datetime import datetime, timezone
from typing import Any

from .prices import Candle

TV_TIMEFRAME = {"M30": "30", "H1": "60", "H4": "240", "D1": "D"}


def _payload(result: Any) -> Any:
    """The tool's data: structured content if present, else the first JSON text block."""
    if getattr(result, "isError", False):
        raise RuntimeError(f"TradingView tool error: {result.content}")
    structured = getattr(result, "structuredContent", None)
    if structured:
        return structured
    for block in result.content:
        text = getattr(block, "text", None)
        if text:
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                return text
    return None


def _ts(v: Any) -> datetime:
    if isinstance(v, (int, float)):
        return datetime.fromtimestamp(v / 1000 if v > 1e11 else v, timezone.utc)
    return datetime.fromisoformat(str(v).replace("Z", "+00:00"))


def parse_bars(data: Any) -> list[Candle]:
    """Accepts {bars|data|ohlcv: [...]}, a list of dicts (time/open/high/low/close or t/o/h/l/c), or a list of arrays."""
    if isinstance(data, dict):
        for key in ("bars", "data", "ohlcv", "candles", "result"):
            if key in data:
                return parse_bars(data[key])
        if all(k in data for k in ("t", "o", "h", "l", "c")):  # column arrays
            return [Candle(_ts(t), float(o), float(h), float(lo), float(c))
                    for t, o, h, lo, c in zip(data["t"], data["o"], data["h"], data["l"], data["c"])]
        raise ValueError(f"unrecognised OHLCV payload keys: {list(data)[:8]}")
    out = []
    for row in data or []:
        if isinstance(row, dict):
            g = lambda *names: next(row[n] for n in names if n in row)  # noqa: E731
            out.append(Candle(_ts(g("time", "timestamp", "t", "datetime")), float(g("open", "o")), float(g("high", "h")),
                              float(g("low", "l")), float(g("close", "c"))))
        else:
            t, o, h, lo, c = row[:5]
            out.append(Candle(_ts(t), float(o), float(h), float(lo), float(c)))
    out.sort(key=lambda c: c.time)
    return out


class TradingViewProvider:
    is_sample = False

    def __init__(self, command: str | None = None) -> None:
        self.command = shlex.split(command or os.environ.get("TAURO_TV_MCP_COMMAND", ""))
        if not self.command:
            raise RuntimeError("Set TAURO_TV_MCP_COMMAND to the command that starts the TradingView connector")

    async def _candles(self, symbol: str, timeframe: str, count: int) -> list[Candle]:
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client

        params = StdioServerParameters(command=self.command[0], args=self.command[1:], env=dict(os.environ))
        async with stdio_client(params) as (read, write), ClientSession(read, write) as session:
            await session.initialize()
            health = await session.call_tool("tv_health_check", {})
            if getattr(health, "isError", False):
                raise RuntimeError("TradingView is unreachable: is the Mac on and TradingView open?")
            state = _payload(await session.call_tool("chart_get_state", {})) or {}
            original_tf = state.get("timeframe") or state.get("interval") if isinstance(state, dict) else None
            chart_symbol = (state.get("symbol") or "") if isinstance(state, dict) else ""
            if chart_symbol and symbol not in chart_symbol.upper().replace(":", ""):
                raise RuntimeError(f"Ali's chart shows {chart_symbol}, not {symbol}; not changing his chart symbol")
            await session.call_tool("chart_set_timeframe", {"timeframe": TV_TIMEFRAME[timeframe]})
            try:
                bars = parse_bars(_payload(await session.call_tool("data_get_ohlcv", {"count": count})))
            finally:
                if original_tf:
                    await session.call_tool("chart_set_timeframe", {"timeframe": str(original_tf)})
        if not bars:
            raise RuntimeError("TradingView returned no bars")
        return bars[-count:]

    def candles(self, symbol: str, timeframe: str, count: int) -> list[Candle]:
        return asyncio.run(self._candles(symbol, timeframe, count))
