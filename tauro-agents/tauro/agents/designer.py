"""Agent 3 · Design Agent. Turns every brief into a finished, on-brand graphic.

Rendering is deterministic code (HTML/CSS → PNG); the brief already picks the template,
so no model call is needed to draw. Canva autofill plugs in here once Tauro's Canva plan is confirmed.
"""
from __future__ import annotations

from pathlib import Path

from ..render.renderer import Renderer
from ..schemas import Brief, Copy, DesignOutput


class DesignerAgent:
    def __init__(self, renderer: Renderer, out_dir: Path) -> None:
        self.renderer, self.out_dir = renderer, out_dir

    def run(self, brief: Brief, copy: Copy, variation: int = 1) -> tuple[DesignOutput, bool]:
        """Returns the design and whether it used sample (non-live) data."""
        if brief.template.value == "gold_chart" and not brief.data.zones:
            from .. import knowledge

            if not knowledge.gold_zones():
                raise ValueError("gold_chart brief has no zones and gold_levels.md has none set")
        images = self.renderer.render(brief, copy, self.out_dir / brief.brief_id, variation=variation)
        sample = brief.template.value == "gold_chart" and self.renderer.prices.is_sample
        return DesignOutput(brief_id=brief.brief_id, template=brief.template, images=[str(p) for p in images],
                            variation=variation), sample
