"""Hard compliance and brand rules, checked by code before the AI review (KNINV build note).

Every rule returns a human-readable reason; an empty list means the post passed.
"""
from __future__ import annotations

import re
from pathlib import Path

from . import knowledge
from .schemas import Brief, Copy, Format, Pillar, Template

OFFER_WORDS = ("bonus", "بونص", "مكافأة", "مكافاة", "spread", "سبريد", "leverage", "رافعة",
               "copy trading", "نسخ الصفقات", "commission", "عمولة", "cashback", "كاش باك", "خصم")

SIZE_FOR_FORMAT = {Format.story: "1080x1920", Format.reel_cover: "1080x1920"}


def required_risk_line(kb_dir: Path | None = None) -> str:
    m = re.search(r"^- AR:\s*(.+)$", knowledge.read("compliance_rules.md", kb_dir), re.M)
    return m.group(1).strip() if m else ""


def approved_offers(kb_dir: Path | None = None) -> list[str]:
    text = knowledge.read("brand_facts.md", kb_dir)
    section = text.split("## Approved offers", 1)[-1]
    section = re.sub(r"<!--.*?-->", "", section, flags=re.S)
    return [ln[2:].strip() for ln in section.splitlines() if ln.startswith("- ")]


def all_text(copy: Copy) -> str:
    parts = [copy.headline, copy.subline, copy.cta, copy.caption, copy.telegram_text, copy.risk_line,
             *copy.bullets, *copy.hooks, *copy.hashtags, *(o.text for o in copy.poll_options)]
    for s in copy.slides:
        parts += [s.headline, s.body]
    for r in copy.calendar:
        parts += [r.event, r.country, r.time]
    return "\n".join(p for p in parts if p)


def hard_checks(brief: Brief, copy: Copy, kb_dir: Path | None = None) -> list[str]:
    reasons: list[str] = []
    text = all_text(copy)
    norm = knowledge.strip_diacritics(text).lower()

    if copy.brief_id != brief.brief_id:
        reasons.append(f"copy brief_id {copy.brief_id!r} does not match brief {brief.brief_id!r}")

    for phrase in knowledge.banned_phrases(kb_dir):
        if phrase in norm:
            reasons.append(f"banned phrase: {phrase!r}")

    risk = required_risk_line(kb_dir)
    if risk and risk not in copy.risk_line:
        reasons.append("risk line missing or not the approved wording from compliance_rules.md")

    official = knowledge.handle(kb_dir).lower()
    for h in re.findall(r"@tauro[\w.]*", text, re.I):
        if h.lower() != official:
            reasons.append(f"handle misspelled: {h} (official: {official})")

    words = len(copy.headline.split())
    if words > 10:
        reasons.append(f"on-image headline is {words} words; keep it to about 8")

    if not 5 <= len(copy.hashtags) <= 10:
        reasons.append(f"{len(copy.hashtags)} hashtags; use 5–10")

    if not copy.cta.strip():
        reasons.append("no CTA")

    expected = SIZE_FOR_FORMAT.get(brief.format, "1080x1350")
    if brief.size != expected:
        reasons.append(f"size {brief.size} is wrong for {brief.format.value}; expected {expected}")

    if brief.pillar == Pillar.market_news and not brief.sources:
        reasons.append("news post has no source link")

    if brief.template == Template.edu_carousel and len(copy.slides) != 4:
        reasons.append(f"carousel needs exactly 4 content slides (Cover → 4 → CTA), got {len(copy.slides)}")
    if brief.template == Template.calendar_card and not copy.calendar:
        reasons.append("calendar card has no events")
    if brief.template == Template.poll_card and len(copy.poll_options) < 2:
        reasons.append("poll needs at least 2 options")

    offers = approved_offers(kb_dir)
    for w in OFFER_WORDS:
        if w in norm and not any(w in o.lower() for o in offers):
            reasons.append(f"mentions an offer ({w!r}) that is not on the approved list in brand_facts.md")

    return reasons


def image_checks(brief: Brief, images: list[Path], sample_data: bool) -> list[str]:
    from PIL import Image

    reasons = []
    if sample_data:
        reasons.append("chart was drawn from SAMPLE price data, not the live MT5 feed")
    w, h = (int(x) for x in brief.size.split("x"))
    for p in images:
        with Image.open(p) as im:
            if im.size != (w, h):
                reasons.append(f"{p.name} is {im.size[0]}x{im.size[1]}, expected {w}x{h}")
    if brief.template == Template.edu_carousel and len(images) != 6:
        reasons.append(f"carousel has {len(images)} slides, expected 6")
    return reasons
