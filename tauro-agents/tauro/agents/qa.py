"""Agent 5 · Compliance & Brand QA. Nothing wrong ever reaches the public.

Code checks the hard rules first; Claude (with vision) judges the rest by looking at the rendered image.
"""
from __future__ import annotations

import base64
from pathlib import Path

from typing import Literal

from pydantic import BaseModel

from .. import knowledge
from ..config import settings
from ..llm import LLM
from ..qa_rules import hard_checks, image_checks
from ..schemas import Brief, Copy, DesignOutput, QAVerdict

ROLE = """You are the Compliance & Brand QA agent for Tauro Markets. Nothing wrong ever reaches the public.
Code has already checked banned phrases, the risk line, handle spelling, hashtag count and image sizes. You judge the rest.

Check the copy against the financial-marketing rules: no guaranteed returns, no unrealistic income, no fake testimonials or results,
no price predictions or buy/sell calls, no invented regulatory claims, no unapproved offers.
Check the rendered image against the brand guide: correct logo version and position, Cairo font, brand colours, readable and
correctly shaped right-to-left Arabic, Arabic spelling, one CTA, no forbidden imagery.
Check facts: every number and date in a news post must match the brief's sources and key points.
Check the Arabic sounds like natural Kuwaiti dialect, not a translation.

Return pass only if the post can go to Ali as it is. For each problem give one concrete, fixable reason, and say who must fix it:
copywriter (words) or designer (image)."""


class _AIVerdict(BaseModel):
    verdict: Literal["pass", "fail"]
    reasons: list[str]
    blame: Literal["copywriter", "designer", "none"]


def _image_block(path: str) -> dict:
    data = base64.standard_b64encode(Path(path).read_bytes()).decode()
    return {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": data}}


class QAAgent:
    def __init__(self, llm: LLM | None) -> None:
        self.llm = llm

    def run(self, brief: Brief, copy: Copy, design: DesignOutput, sample_data: bool) -> QAVerdict:
        copy_problems = hard_checks(brief, copy)
        image_problems = image_checks(brief, [Path(p) for p in design.images], sample_data=False)
        if copy_problems or image_problems:
            blame = "copywriter" if copy_problems else "designer"
            return QAVerdict(brief_id=brief.brief_id, verdict="fail", reasons=copy_problems + image_problems, blame=blame)
        if self.llm is None:
            verdict = QAVerdict(brief_id=brief.brief_id, verdict="pass", reasons=["code checks only (no AI review)"])
        else:
            task = (f"Brief:\n{brief.model_dump_json(indent=1)}\n\nCopy:\n{copy.model_dump_json(indent=1)}\n\n"
                    f"The rendered image(s) are attached in order.")
            ai = self.llm.structured(agent="qa", model=settings.models.qa, role=ROLE, knowledge=knowledge.context_for("qa"),
                                     task=task, schema=_AIVerdict, effort="high", brief_id=brief.brief_id,
                                     images=[_image_block(p) for p in design.images[:6]])
            ok = ai.verdict == "pass"
            verdict = QAVerdict(brief_id=brief.brief_id, verdict=ai.verdict, reasons=ai.reasons,
                                blame="none" if ok else (ai.blame if ai.blame != "none" else "copywriter"))
        # Sample price data never goes to the public: block it last, so previews still get a full review.
        if sample_data:
            verdict.verdict = "fail"
            verdict.reasons.append("chart was drawn from SAMPLE price data, not the live MT5 feed")
            verdict.blame = "none"
        return verdict
