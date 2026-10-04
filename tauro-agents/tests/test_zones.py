from datetime import date, datetime, timedelta, timezone

from tauro.data.prices import Candle, SampleProvider
from tauro.zones import derive_zones, is_stale, pivots


def bars(closes):
    t0 = datetime(2026, 10, 1, tzinfo=timezone.utc)
    out = []
    for i, c in enumerate(closes):
        out.append(Candle(t0 + timedelta(hours=4 * i), c, c + 1, c - 1, c))
    return out


def test_pivots_find_swing_points():
    highs, lows = pivots(bars([10, 12, 15, 12, 10, 8, 5, 8, 10, 12]))
    assert highs == [16] and lows == [4]


def test_zones_sit_above_and_below_price_within_band_limits():
    zones = derive_zones(SampleProvider().candles("XAUUSD", "H4", 60))
    price = SampleProvider().candles("XAUUSD", "H4", 60)[-1].close
    assert zones, "sample data should produce at least one zone"
    for z in zones:
        assert 15 <= round(z.high - z.low, 2) <= 25
        assert (z.low > price) if z.kind == "supply" else (z.high < price)


def test_staleness():
    today = date(2026, 10, 4)
    assert is_stale(None, today)
    assert is_stale(date(2026, 9, 1), today)
    assert not is_stale(date(2026, 9, 30), today)


def test_chart_without_zones_gets_auto_zones_and_a_note(sample):
    from tauro.render.renderer import Renderer

    brief, copy = sample("gold_chart")
    brief.data.zones = []
    page = Renderer(SampleProvider()).pages(brief, copy)[0]
    assert page.notes and "auto-derived" in page.notes[0]
