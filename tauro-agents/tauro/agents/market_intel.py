"""Agent 1 · Market Intelligence & News. Knows what is moving the markets and what GCC traders talk about."""
from __future__ import annotations

from datetime import datetime

from .. import knowledge
from ..config import KUWAIT, settings
from ..data.prices import BigMove, PriceProvider, big_moves
from ..llm import LLM, web_search_tool
from ..schemas import MarketBrief

ROLE = """You are the Market Intelligence & News agent for Tauro Markets, a multi-asset broker for traders in Kuwait and the GCC.
Your job: find what is moving the markets right now and what Arabic-speaking traders in the GCC are talking about.

Cover: central banks (Fed, ECB and others), US data, geopolitics, oil, wars, sanctions, elections, tariffs.
Use official sources first (federalreserve.gov, ecb.europa.eu, bls.gov, bea.gov and other central banks or statistics offices), then reputable news.
Rate every item: impact (high/medium/low), relevance to Tauro's GCC audience, urgency (now / today / this_week).
Economic calendar: keep only the highest-impact (3-star) events, with Kuwait times (UTC+3).

Rules:
- Facts only. Every item has a working source_url that supports it.
- Never predict prices and never give buy/sell calls.
- Never copy another channel's analysis or levels.
- summary_ar is a short summary for Ali in Kuwaiti Arabic.
- Set breaking=true only for a surprise with high market impact (surprise rate decision, sharp gold move, war news)."""


def moves_text(moves: list[BigMove]) -> str:
    if not moves:
        return "No watchlist symbol crossed its big-move threshold."
    return "\n".join(f"- {m.symbol} moved {m.change_pct:+.2f}% in {m.hours}h (threshold ±{m.threshold_pct}%)" for m in moves)


class MarketIntelAgent:
    def __init__(self, llm: LLM, prices: PriceProvider) -> None:
        self.llm, self.prices = llm, prices

    def run(self, kind: str = "brief", now: datetime | None = None) -> MarketBrief:
        """kind: 'brief' for the 06:00/07:00 and 12:00 runs, 'scan' for the 30-minute checks."""
        now = now or datetime.now(KUWAIT)
        moves = big_moves(self.prices, knowledge.watchlist())
        sample_note = "\n(Price moves come from SAMPLE data in this environment; do not report them as real.)" if self.prices.is_sample else ""
        if kind == "scan":
            model, effort = settings.models.market_scan, "low"
            task = (f"Now: {now:%A %Y-%m-%d %H:%M} Kuwait time.\nQuick 30-minute scan: anything new and high-impact since the last 30 minutes?\n"
                    f"Watchlist moves (computed in code):\n{moves_text(moves)}{sample_note}\n"
                    "Return only items from the last hour. Leave calendar_today empty.")
        else:
            model, effort = settings.models.market_brief, "medium"
            task = (f"Now: {now:%A %Y-%m-%d %H:%M} Kuwait time.\nWrite the Market Brief: overnight news, Asia session recap, today's and this week's "
                    f"3-star calendar events, and trending trading topics in Arabic on X, YouTube, TikTok and Instagram for Kuwait, Saudi Arabia and the UAE.\n"
                    f"Watchlist moves (computed in code):\n{moves_text(moves)}{sample_note}")
        brief = self.llm.structured(agent="market_intel", model=model, role=ROLE, knowledge=knowledge.context_for("market_intel"),
                                    task=task, schema=MarketBrief, effort=effort, tools=[web_search_tool(model)])
        if moves and not self.prices.is_sample:
            brief.breaking = brief.breaking or any(m.symbol == "XAUUSD" for m in moves)
        return brief
