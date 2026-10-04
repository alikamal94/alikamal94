"""Deterministic rendering: template HTML/CSS → PNG with headless Chromium (Playwright)."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from .. import knowledge
from ..config import settings
from ..data.prices import PriceProvider
from ..schemas import Brief, Copy, Pillar, Template
from .chart import candle_svg

TEMPLATES_DIR = Path(__file__).parent / "templates"
ARABIC_DIGITS = str.maketrans("0123456789", "٠١٢٣٤٥٦٧٨٩")

KICKER = {
    Pillar.market_news: "أخبار السوق",
    Pillar.education: "تعليم",
    Pillar.gold_analysis: "تحليل الذهب",
    Pillar.workshop: "ورشة مجانية",
    Pillar.trust: "قيمنا",
    Pillar.engagement: "شاركنا رأيك",
}


def to_arabic_digits(text: str) -> str:
    """Brand rule: Arabic-Indic numerals in Arabic copy."""
    return str(text).translate(ARABIC_DIGITS)


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


class Renderer:
    def __init__(self, prices: PriceProvider, kb_dir: Path | None = None) -> None:
        self.prices = prices
        self.kb_dir = kb_dir
        self.env = Environment(loader=FileSystemLoader(TEMPLATES_DIR), undefined=StrictUndefined, autoescape=True)
        self.env.filters["ar"] = to_arabic_digits

    def _logo(self, theme: str) -> str:
        name = "tauro-logo-primary.png" if theme == "white" else "tauro-logo-reversed.png"
        return (settings.assets_dir / "logo" / name).as_uri()

    def pages(self, brief: Brief, copy: Copy) -> list[RenderedPage]:
        w, h = (int(x) for x in brief.size.split("x"))
        theme = theme_for(brief)
        sample = False
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
            zones = brief.data.zones or knowledge.gold_zones(self.kb_dir)
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
        return [RenderedPage(tpl.render(**base), w, h)]

    def render(self, brief: Brief, copy: Copy, out_dir: Path, variation: int = 1) -> list[Path]:
        from playwright.sync_api import sync_playwright

        out_dir = out_dir.resolve()
        out_dir.mkdir(parents=True, exist_ok=True)
        pages = self.pages(brief, copy)
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
