"""Agent 4 · Arabic Copywriter. Writes like a Kuwaiti trader, not a translation."""
from __future__ import annotations

from .. import knowledge
from ..config import settings
from ..llm import LLM
from ..schemas import Brief, Copy, Template

ROLE = """You are the Arabic Copywriter for Tauro Markets. You write words that sound like a Kuwaiti trader, not a translation.

For each brief write: the on-image headline (about 8 words max), subline, caption, hook line(s), one CTA, and 5–10 hashtags.
- Arabic-first, in natural Gulf (Kuwaiti) dialect. Formal Arabic only for official announcements.
- Never translate word for word from English. Rewrite the idea the way a Kuwaiti trader would say it.
- Telegram posts (telegram_text) are in Kuwaiti dialect in the approved gold-post format.
- Give 2 hook options for Reels and key posts (variations=2).
- Copy the required risk line from compliance_rules.md exactly into risk_line.
- No profit promises, no "guaranteed", no income claims, no buy/sell calls. Levels are areas to watch, not instructions.
- Never mention an offer that is not on the approved list in brand_facts.md.
- Spell the Instagram handle exactly as in brand_facts.md.

Template fields:
- news_card / workshop_promo: up to 4 short bullets.
- edu_carousel: exactly 4 slides (headline + body each); the cover uses headline/subline and the last slide uses cta.
- calendar_card: one calendar row per 3-star event (time in Kuwait time with the day, country with flag, event name).
- poll_card: 2–4 poll_options.
- gold_chart / tip_card: headline + subline only."""


class CopywriterAgent:
    def __init__(self, llm: LLM) -> None:
        self.llm = llm

    def run(self, brief: Brief, feedback: list[str] | None = None) -> Copy:
        task = f"Brief:\n{brief.model_dump_json(indent=1)}"
        if brief.template == Template.calendar_card:
            task += "\nUse only the events listed in key_points or sources; do not invent events or times."
        if feedback:
            task += "\n\nQA rejected the previous version. Fix exactly these problems:\n" + "\n".join(f"- {r}" for r in feedback)
        copy = self.llm.structured(agent="copywriter", model=settings.models.copywriter, role=ROLE,
                                   knowledge=knowledge.context_for("copywriter"), task=task, schema=Copy,
                                   effort="medium", brief_id=brief.brief_id)
        copy.brief_id = brief.brief_id
        return copy
