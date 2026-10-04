"""Structured handoffs between agents (build spec: "Handoff format").

Agents never talk to each other directly: each agent's validated JSON is stored
and becomes the next agent's input.
"""
from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class Priority(str, Enum):
    normal = "normal"
    breaking = "breaking"


class Channel(str, Enum):
    instagram_feed = "instagram_feed"
    instagram_story = "instagram_story"
    telegram = "telegram"


class Format(str, Enum):
    single_post = "single_post"
    carousel = "carousel"
    story = "story"
    reel_cover = "reel_cover"
    telegram_card = "telegram_card"


class Template(str, Enum):
    news_card = "news_card"
    gold_chart = "gold_chart"
    calendar_card = "calendar_card"
    edu_carousel = "edu_carousel"
    tip_card = "tip_card"
    workshop_promo = "workshop_promo"
    poll_card = "poll_card"


class Pillar(str, Enum):
    market_news = "market_news"
    education = "education"
    gold_analysis = "gold_analysis"
    workshop = "workshop"
    trust = "trust"
    engagement = "engagement"


class Goal(str, Enum):
    awareness = "awareness"
    engagement = "engagement"
    website_click = "website_click"
    workshop_booking = "workshop_booking"


class Zone(BaseModel):
    kind: Literal["supply", "demand"]
    low: float
    high: float
    label: str = ""


class BriefData(BaseModel):
    symbol: str = ""
    timeframe: str = ""
    zones: list[Zone] = Field(default_factory=list)


class Brief(BaseModel):
    """The creative brief the Strategist sends to the Copywriter and Designer."""

    brief_id: str = Field(description="YYYY-MM-DD-NN")
    priority: Priority = Priority.normal
    publish_at: str = Field(description="ISO 8601 with +03:00 offset")
    channels: list[Channel]
    format: Format
    size: Literal["1080x1350", "1080x1920"] = "1080x1350"
    template: Template
    pillar: Pillar
    goal: Goal
    topic: str
    key_points: list[str]
    data: BriefData = Field(default_factory=BriefData)
    sources: list[str] = Field(default_factory=list)
    cta: str
    visual_direction: str = ""
    variations: int = Field(default=1, ge=1, le=2)


class ContentPlan(BaseModel):
    date: str
    notes: str = ""
    briefs: list[Brief]


class Slide(BaseModel):
    headline: str
    body: str = ""


class CalendarRow(BaseModel):
    time: str
    country: str
    event: str


class PollOption(BaseModel):
    text: str


class Copy(BaseModel):
    """Copywriter output. on_image goes to the Designer; everything goes to QA."""

    brief_id: str
    headline: str = Field(description="On-image headline, about 8 words max")
    subline: str = Field(default="", description="Supporting line under the headline")
    bullets: list[str] = Field(default_factory=list)
    slides: list[Slide] = Field(default_factory=list, description="Carousels only: 4 content slides")
    calendar: list[CalendarRow] = Field(default_factory=list)
    poll_options: list[PollOption] = Field(default_factory=list)
    cta: str
    caption: str
    hooks: list[str] = Field(default_factory=list)
    hashtags: list[str]
    risk_line: str = ""
    telegram_text: str = ""


class DesignOutput(BaseModel):
    brief_id: str
    template: Template
    images: list[str]
    canva_edit_link: str = ""
    variation: int = 1


class QAVerdict(BaseModel):
    brief_id: str
    verdict: Literal["pass", "fail"]
    reasons: list[str] = Field(default_factory=list)
    blame: Literal["copywriter", "designer", "none"] = "none"


class MarketItem(BaseModel):
    headline: str
    summary: str
    source_url: str
    impact: Literal["high", "medium", "low"]
    relevance: Literal["high", "medium", "low"]
    urgency: Literal["now", "today", "this_week"]
    symbols: list[str] = Field(default_factory=list)


class CalendarEvent(BaseModel):
    time_kuwait: str
    country: str
    event: str
    source_url: str = ""


class MarketBrief(BaseModel):
    date: str
    items: list[MarketItem]
    calendar_today: list[CalendarEvent] = Field(default_factory=list)
    trending_topics: list[str] = Field(default_factory=list)
    summary_ar: str = Field(description="Short Arabic summary for Ali")
    breaking: bool = False
