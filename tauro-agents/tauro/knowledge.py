"""Shared knowledge base: the files every agent reads before it works."""
from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

from .config import settings
from .schemas import Zone

# Which files each agent reads (build spec, "Shared knowledge base").
AGENT_FILES: dict[str, list[str]] = {
    "market_intel": ["watchlist.md", "audience.md"],
    "strategist": ["brand_facts.md", "gold_levels.md", "audience.md", "content_calendar.md", "performance_memory.md", "compliance_rules.md"],
    "copywriter": ["voice_guide.md", "compliance_rules.md", "brand_facts.md", "audience.md", "gold_levels.md"],
    "designer": ["brand_guide.md", "brand_facts.md", "gold_levels.md"],
    "qa": ["compliance_rules.md", "brand_guide.md", "voice_guide.md", "brand_facts.md"],
    "competitor": ["competitors.md"],
}


def read(name: str, kb_dir: Path | None = None) -> str:
    return ((kb_dir or settings.knowledge_dir) / name).read_text(encoding="utf-8")


def context_for(agent: str, kb_dir: Path | None = None) -> str:
    """All of an agent's KB files joined in a fixed order, so the prompt prefix stays cacheable."""
    parts = [f"<file name=\"{n}\">\n{read(n, kb_dir)}\n</file>" for n in AGENT_FILES[agent]]
    return "\n\n".join(parts)


def _block(text: str, tag: str) -> list[str]:
    m = re.search(rf"```{tag}\n(.*?)```", text, re.S)
    if not m:
        return []
    return [ln.strip() for ln in m.group(1).splitlines() if ln.strip()]


def strip_diacritics(s: str) -> str:
    return re.sub(r"[ً-ْٰـ]", "", s)


@lru_cache
def banned_phrases(kb_dir: Path | None = None) -> tuple[str, ...]:
    return tuple(strip_diacritics(p).lower() for p in _block(read("compliance_rules.md", kb_dir), "banned"))


def handle(kb_dir: Path | None = None) -> str:
    m = re.search(r"Instagram handle:\s*\*\*(@[\w.]+)\*\*", read("brand_facts.md", kb_dir))
    if not m:
        raise ValueError("brand_facts.md has no 'Instagram handle: **@...**' line")
    return m.group(1)


def gold_zones(kb_dir: Path | None = None) -> list[Zone]:
    zones = []
    for line in _block(read("gold_levels.md", kb_dir), "zones"):
        kind, low, high = (p.strip() for p in line.split("|"))
        lo, hi = float(low), float(high)
        if lo == 0 and hi == 0:
            continue
        zones.append(Zone(kind=kind, low=min(lo, hi), high=max(lo, hi)))
    return zones


def watchlist(kb_dir: Path | None = None) -> list[tuple[str, float, int]]:
    rows = []
    for line in _block(read("watchlist.md", kb_dir), "watchlist"):
        sym, pct, hours = (p.strip() for p in line.split("|"))
        rows.append((sym, float(pct), int(hours)))
    return rows
