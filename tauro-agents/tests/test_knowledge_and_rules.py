import pytest

from tauro import knowledge
from tauro.qa_rules import hard_checks, required_risk_line
from tauro.schemas import Format

ALL = ["news_card", "gold_chart", "calendar_card", "tip_card", "workshop_promo", "poll_card", "edu_carousel"]


def test_knowledge_parsing():
    assert knowledge.handle() == "@tauromarkets_me"
    assert "guaranteed" in knowledge.banned_phrases()
    assert knowledge.gold_zones() == []  # placeholder zones (0 | 0) are ignored until Ali sets real ones
    assert ("XAUUSD", 1.0, 4) in knowledge.watchlist()
    assert required_risk_line().startswith("التداول ينطوي")


@pytest.mark.parametrize("name", ALL)
def test_samples_pass_hard_rules(sample, name):
    brief, copy = sample(name)
    assert hard_checks(brief, copy) == []


def test_banned_phrase_even_with_diacritics(sample):
    brief, copy = sample("news_card")
    copy.caption += " ربح مَضْمُون"
    assert any("banned phrase" in r for r in hard_checks(brief, copy))


def test_wrong_handle(sample):
    brief, copy = sample("news_card")
    copy.caption += " تابعونا @tauromarketsme"
    assert any("handle misspelled" in r for r in hard_checks(brief, copy))


def test_missing_risk_line(sample):
    brief, copy = sample("gold_chart")
    copy.risk_line = ""
    assert any("risk line" in r for r in hard_checks(brief, copy))


def test_unapproved_offer(sample):
    brief, copy = sample("workshop_promo")
    copy.bullets.append("بونص ٥٠٪ على أول إيداع")
    assert any("offer" in r for r in hard_checks(brief, copy))


def test_story_size_and_news_sources(sample):
    brief, copy = sample("news_card")
    brief.sources = []
    brief.format = Format.story
    reasons = hard_checks(brief, copy)
    assert any("source link" in r for r in reasons)
    assert any("expected 1080x1920" in r for r in reasons)


def test_carousel_needs_four_slides(sample):
    brief, copy = sample("edu_carousel")
    copy.slides = copy.slides[:3]
    assert any("4 content slides" in r for r in hard_checks(brief, copy))
