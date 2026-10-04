"""Price feeds. Production uses Tauro's own MT5 feed; tests and previews use sample data.

Anything rendered from sample data is stamped "SAMPLE DATA" and QA blocks it, so
made-up prices can never reach the public.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Protocol

TIMEFRAME_HOURS = {"M30": 0.5, "H1": 1, "H4": 4, "D1": 24}


@dataclass(frozen=True)
class Candle:
    time: datetime
    open: float
    high: float
    low: float
    close: float


class PriceProvider(Protocol):
    is_sample: bool

    def candles(self, symbol: str, timeframe: str, count: int) -> list[Candle]: ...


SAMPLE_BASE = {"XAUUSD": 2650.0, "EURUSD": 1.08, "GBPUSD": 1.27, "USDJPY": 148.0,
               "US30": 42000.0, "NAS100": 19500.0, "USOIL": 72.0, "BTCUSD": 63000.0}


class SampleProvider:
    """Deterministic random walk, for development only."""

    is_sample = True

    def candles(self, symbol: str, timeframe: str, count: int) -> list[Candle]:
        rng = random.Random(f"{symbol}-{timeframe}-{count}")
        step = timedelta(hours=TIMEFRAME_HOURS[timeframe])
        price = SAMPLE_BASE.get(symbol, 100.0)
        vol = price * 0.004 * math.sqrt(TIMEFRAME_HOURS[timeframe])
        start = datetime(2026, 9, 1, tzinfo=timezone.utc)
        out = []
        for i in range(count):
            o = price
            c = o + rng.gauss(0, vol)
            h = max(o, c) + abs(rng.gauss(0, vol * 0.5))
            lo = min(o, c) - abs(rng.gauss(0, vol * 0.5))
            out.append(Candle(start + i * step, round(o, 5), round(h, 5), round(lo, 5), round(c, 5)))
            price = c
        return out


class MT5Provider:
    """Tauro's MT5 feed via the MetaTrader5 package (needs a Windows host with the MT5 terminal).

    Set MT5_LOGIN, MT5_PASSWORD (investor / read-only) and MT5_SERVER.
    """

    is_sample = False

    def __init__(self) -> None:
        import os

        import MetaTrader5 as mt5  # type: ignore[import-not-found]

        self.mt5 = mt5
        if not mt5.initialize(login=int(os.environ["MT5_LOGIN"]), password=os.environ["MT5_PASSWORD"],
                              server=os.environ["MT5_SERVER"]):
            raise RuntimeError(f"MT5 initialize failed: {mt5.last_error()}")

    def candles(self, symbol: str, timeframe: str, count: int) -> list[Candle]:
        tf = getattr(self.mt5, f"TIMEFRAME_{timeframe}")
        rates = self.mt5.copy_rates_from_pos(symbol, tf, 0, count)
        if rates is None:
            raise RuntimeError(f"MT5 returned no data for {symbol}: {self.mt5.last_error()}")
        return [Candle(datetime.fromtimestamp(int(r["time"]), timezone.utc), float(r["open"]),
                       float(r["high"]), float(r["low"]), float(r["close"])) for r in rates]


def get_provider(name: str) -> PriceProvider:
    if name == "mt5":
        return MT5Provider()
    if name == "tradingview":
        from .tradingview import TradingViewProvider

        return TradingViewProvider()
    if name == "sample":
        return SampleProvider()
    raise ValueError(f"unknown price provider {name!r}")


@dataclass(frozen=True)
class BigMove:
    symbol: str
    change_pct: float
    hours: int
    threshold_pct: float


def big_moves(provider: PriceProvider, watchlist: list[tuple[str, float, int]]) -> list[BigMove]:
    """Flag any symbol that moved more than its threshold over its lookback (plain code, no AI)."""
    moves = []
    for symbol, threshold, hours in watchlist:
        bars = provider.candles(symbol, "M30", hours * 2 + 1)
        first, last = bars[0].open, bars[-1].close
        change = (last - first) / first * 100
        if abs(change) >= threshold:
            moves.append(BigMove(symbol, round(change, 2), hours, threshold))
    return moves
