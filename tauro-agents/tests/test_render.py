import pytest
from PIL import Image

from tauro.data.prices import SampleProvider
from tauro.render.renderer import Renderer, theme_for, to_arabic_digits


def test_arabic_digits():
    assert to_arabic_digits("17:30 – 19:30") == "١٧:٣٠ – ١٩:٣٠"


def test_themes_follow_grid(sample):
    assert theme_for(sample("edu_carousel")[0]) == "dark"
    assert theme_for(sample("tip_card")[0]) == "white"
    assert theme_for(sample("workshop_promo")[0]) == "red"


def test_carousel_is_cover_four_slides_red_cta(sample):
    pages = Renderer(SampleProvider()).pages(*sample("edu_carousel"))
    assert len(pages) == 6
    assert 'class="theme-red"' in pages[-1].html
    assert all('class="theme-dark"' in p.html for p in pages[:5])


def test_page_has_brand_basics(sample):
    page = Renderer(SampleProvider()).pages(*sample("news_card"))[0]
    assert 'dir="rtl"' in page.html
    assert "tauro-logo-reversed.png" in page.html
    assert "@tauromarkets_me" in page.html
    assert "Cairo-Bold.ttf" in page.html


def test_white_theme_uses_primary_logo(sample):
    page = Renderer(SampleProvider()).pages(*sample("tip_card"))[0]
    assert "tauro-logo-primary.png" in page.html


def test_sample_chart_is_stamped(sample):
    page = Renderer(SampleProvider()).pages(*sample("gold_chart"))[0]
    assert "SAMPLE DATA" in page.html
    assert "<svg" in page.html


@pytest.mark.slow
@pytest.mark.parametrize("name,size,count", [("news_card", (1080, 1350), 1), ("poll_card", (1080, 1920), 1),
                                             ("edu_carousel", (1080, 1350), 6)])
def test_png_output(sample, tmp_path, name, size, count):
    paths = Renderer(SampleProvider()).render(*sample(name), tmp_path)
    assert len(paths) == count
    for p in paths:
        with Image.open(p) as im:
            assert im.size == size
