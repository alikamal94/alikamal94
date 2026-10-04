"""Deterministic rendering: template HTML/CSS → PNG with headless Chromium (Playwright)."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from .. import knowledge
from ..config import settings
from ..data.prices import PriceProvider
from ..schemas import Brief, Copy, Pillar, Template
from .chart import candle_svg
from ..zones import derive_zones, is_stale

TEMPLATES_DIR = Path(__file__).parent / "templates"
# A number range such as "17:30 – 19:30" or "4455-4475" flips inside right-to-left text; isolating it keeps it in order.
NUMBER_RANGE = re.compile(r"\d[\d.,:]*\s*[–—-]\s*\d[\d.,:]*")
LRI, PDI = "\u2066", "\u2069"


def keep_ranges_ltr(text: str) -> str:
    return NUMBER_RANGE.sub(lambda m: f"{LRI}{m.group(0)}{PDI}", text)


def _fix_copy(copy: Copy) -> Copy:
    def walk(v):
        if isinstance(v, str):
            return keep_ranges_ltr(v)
        if isinstance(v, list):
            return [walk(x) for x in v]
        if isinstance(v, dict):
            return {k: walk(x) for k, x in v.items()}
        return v

    return Copy.model_validate(walk(copy.model_dump()))

KICKER = {
    Pillar.market_news: "أخبار السوق",
    Pillar.education: "تعليم",
    Pillar.gold_analysis: "تحليل الذهب",
    Pillar.workshop: "ورشة مجانية",
    Pillar.trust: "قيمنا",
    Pillar.engagement: "شاركنا رأيك",
}


def theme_for(brief: Brief) -> str:
    """3-pillar grid: dark for analysis/education, white for trust, red for promo."""
    if brief.pillar == Pillar.trust or brief.template == Template.tip_card:
        return "white"
    if brief.pillar == Pillar.workshop or brief.template == Template.workshop_promo:
        return "red"
    return "dark"


@dataclass
class RenderedPage:
    html: str
    width: int
    height: int
    notes: list[str] = field(default_factory=list)


class Renderer:
    def __init__(self, prices: PriceProvider, kb_dir: Path | None = None, today: date | None = None) -> None:
        self.prices = prices
        self.kb_dir = kb_dir
        self.today = today
        self.last_notes: list[str] = []
        self.env = Environment(loader=FileSystemLoader(TEMPLATES_DIR), undefined=StrictUndefined, autoescape=True)

    def _logo(self, theme: str) -> str:
        name = "tauro-logo-primary.png" if theme == "white" else "tauro-logo-reversed.png"
        return (settings.assets_dir / "logo" / name).as_uri()

    def pages(self, brief: Brief, copy: Copy) -> list[RenderedPage]:
        w, h = (int(x) for x in brief.size.split("x"))
        theme = theme_for(brief)
        copy = _fix_copy(copy)
        sample = False
        notes: list[str] = []
        base = dict(
            w=w, h=h, theme=theme, logo=self._logo(theme),
            fonts=(settings.assets_dir / "fonts").as_uri(),
            handle=knowledge.handle(self.kb_dir), kicker=KICKER[brief.pillar],
            risk_line=copy.risk_line, copy=copy, headline_size=84 if h > 1400 else 72,
            sources=[s.split("/")[2] if "://" in s else s for s in brief.sources],
        )

        if brief.template == Template.gold_chart:
            symbol = brief.data.symbol or "XAUUSD"
            timeframe = brief.data.timeframe or "H4"
            candles = self.prices.candles(symbol, timeframe, 60)
            sample = self.prices.is_sample
            zones = brief.data.zones
            if not zones:
                kb_zones = knowledge.gold_zones(self.kb_dir)
                if kb_zones and not is_stale(knowledge.gold_levels_updated(self.kb_dir), self.today or date.today()):
                    zones = kb_zones
                else:
                    zones = derive_zones(candles)
                    shown = ", ".join(f"{z.kind} {z.low:.2f}–{z.high:.2f}" for z in zones) or "none found"
                    notes.append(f"Zones auto-derived from H4 swings and unconfirmed ({shown}). "
                                 "Confirm or replace them in gold_levels.md.")
            chart_h = 1000 if h > 1400 else 440
            base |= dict(symbol=symbol, timeframe=timeframe,
                         chart_svg=candle_svg(candles, zones, width=w - 2 * 72 - 48, height=chart_h))
        base["sample"] = sample

        if brief.template == Template.edu_carousel:
            if len(copy.slides) != 4:
                raise ValueError(f"edu_carousel needs exactly 4 content slides, got {len(copy.slides)}")
            tpl = self.env.get_template("edu_slide.html")
            out = [RenderedPage(tpl.render(**base, slide_kind="cover", slide_index=0), w, h)]
            for i, s in enumerate(copy.slides, start=1):
                out.append(RenderedPage(tpl.render(**base, slide_kind="content", slide=s, slide_no=i, slide_index=i), w, h))
            # The CTA slide is always red.
            cta_base = base | dict(theme="red", logo=self._logo("red"))
            out.append(RenderedPage(tpl.render(**cta_base, slide_kind="cta", slide_index=5), w, h))
            return out

        tpl = self.env.get_template(f"{brief.template.value}.html")
        return [RenderedPage(tpl.render(**base), w, h, notes)]

    def render(self, brief: Brief, copy: Copy, out_dir: Path, variation: int = 1) -> list[Path]:
        from playwright.sync_api import sync_playwright

        out_dir = out_dir.resolve()
        out_dir.mkdir(parents=True, exist_ok=True)
        pages = self.pages(brief, copy)
        self.last_notes = [n for p in pages for n in p.notes]
        paths = []
        with sync_playwright() as p:
            browser = p.chromium.launch(executable_path=settings.chromium_path or None)
            try:
                for i, page_def in enumerate(pages, start=1):
                    html_path = out_dir / f"{brief.brief_id}-v{variation}-{i}.html"
                    html_path.write_text(page_def.html, encoding="utf-8")
                    page = browser.new_page(viewport={"width": page_def.width, "height": page_def.height})
                    page.goto(html_path.as_uri())
                    page.evaluate("document.fonts.ready")
                    png = out_dir / f"{brief.brief_id}-v{variation}-{i}.png"
                    page.screenshot(path=str(png), full_page=False)
                    page.close()
                    paths.append(png)
            finally:
                browser.close()
        return paths
