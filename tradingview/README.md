# IFVG Sniper Model (TradingView / Pine Script v6)

`ifvg-sniper.pine` marks one complete IFVG setup at a time for each direction, step by step:

| # | Step | Bullish rule (bearish is the mirror) |
|---|------|--------------------------------------|
| 1 | **Liquidity sweep** | Price wicks below an untouched swing low (sell-side liquidity), then closes back above it. |
| 2 | **V-shape recovery** | Within `Max bars from extreme → recovery`, price rallies at least `Recovery displacement × ATR` off the sweep low and closes back above the swept level. |
| 3 | **CISD** | A candle closes above the open of the run of down-close candles that delivered price into the low. |
| 4 | **IFVG (sniper zone)** | A bearish FVG that formed during the sell-off (up to `N` bars before the sweep) gets a candle close above its top. The FVG has now inverted and becomes support. When steps 2–4 all line up within `Max bars sweep → CISD & IFVG`, the IFVG box is drawn and the setup is **armed**. |
| 5 | **Retest + second sweep** | Price comes back into the IFVG, takes out the low of the previous `N` bars (minor liquidity), and closes back above that low without closing below the IFVG. This is the **BUY** signal, and entry is at that candle's close. |
| 6 | **Targets** | By default TP1 is at 1R and TP2 at 2R. The stop goes below the retest-sweep low plus a small ATR buffer. At TP1, 50% is closed and the stop moves to entry. In `Liquidity (capped at R:R)` mode, each target is the nearest untouched swing or previous-day level, but never further than 1R / 2R. |

### High-probability filters (defaults tuned for the 15M chart)
- **HTF bias:** longs only when the 1H close is above a rising 50 EMA; shorts only below a falling one. It uses the last closed 1H bar, so it doesn't repaint.
- **Killzones:** entries only during London (02:00–05:00 New York time) and New York (07:00–11:00).
- **Major liquidity only:** swing length is 8, and the previous day's high and low are added as liquidity pools.
- **Displacement:** the candle that inverts the FVG must have a body of at least 50% of its range.
- **Stop size:** a retest is skipped if its stop would be larger than 2× ATR. Stops tighter than 0.3× ATR are widened so normal noise doesn't hit them.
- **Draw on liquidity:** the trade is only taken if there's an untouched liquidity pool at least TP1 away in the trade direction.

A retest that fails a filter is skipped, and the IFVG stays armed for a later retest.

A setup is cancelled if price:
- makes a new extreme before all confirmations are in,
- closes back through the far side of the IFVG,
- breaks the original sweep extreme, or
- runs out of time at any step.

Cancelled IFVG boxes turn grey. Trades still open after 96 bars (one day on 15M) are closed at market.

## Install
1. In TradingView, open **Pine Editor** and create a new blank indicator.
2. Paste in the contents of `ifvg-sniper.pine`, then click **Save** and **Add to chart**.
3. To set alerts, go to **Alerts → Create alert**, choose `IFVG Sniper`, and pick one of these:
   - one of the named conditions (armed, entry, TP1, TP2, stop), or
   - **Any alert() function call**, which gives you an entry message that includes the SL, TP1 and TP2 prices.

## Chart legend
- **Dotted grey rays:** resting liquidity pools. Each ray stops at the bar where its pool is taken.
- **SSL / BSL sweep, V, CISD:** labels placed after the fact on the bars that confirmed each step.
- **⌖ IFVG box:** the sniper entry zone. Its border gets thicker when the retest fires.
- **BUY / SELL label:** the confirmed entry. Hover over it to see entry, SL, TP1, TP2 and R:R.
- **Entry / SL / TP1 / TP2 lines (labelled with their R):** these follow the trade until it ends. If `Move SL to entry after TP1` is on, the SL moves to break-even once TP1 is hit.
- **Stats table (top right):** closed trades, win rate (R > 0), TP1 and TP2 hit rates, stops before TP1, net R and average R per trade. These are for the bars loaded on your chart.

## Tuning tips
Check **Win rate** and **Avg R** in the stats table on the 15M chart with about 2–3 months of history loaded, then:
- **Win rate too low:** turn on `Move SL to entry after TP1` if it's off, raise `Min body %` to 0.6, raise `Liquidity swing length` to 10, or narrow the killzones.
- **Too few trades:** turn off `Require draw on liquidity beyond TP1`, raise `Skip entry if stop > N × ATR` to 2.5, or turn off the HTF filter.
- **Want more R per trade:** set `Close % at TP1` to 0 (then TP1 only moves the stop to break-even) or raise TP2.

This is a study tool, not financial advice.
