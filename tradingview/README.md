# IFVG Sniper Model (TradingView / Pine Script v6)

`ifvg-sniper.pine` marks one complete IFVG setup at a time for each direction, step by step:

| # | Step | Bullish rule (bearish is the mirror) |
|---|------|--------------------------------------|
| 1 | **Liquidity sweep** | Price wicks below an untouched swing low (sell-side liquidity), then closes back above it. |
| 2 | **V-shape recovery** | Within `Max bars from extreme → recovery`, price rallies at least `Recovery displacement × ATR` off the sweep low and closes back above the swept level. |
| 3 | **CISD** | A candle closes above the open of the run of down-close candles that delivered price into the low. |
| 4 | **IFVG (sniper zone)** | A bearish FVG that formed during the sell-off (up to `N` bars before the sweep) gets a candle close above its top. The FVG has now inverted and becomes support. When steps 2–4 all line up within `Max bars sweep → CISD & IFVG`, the IFVG box is drawn and the setup is **armed**. |
| 5 | **Retest + second sweep** | Price comes back into the IFVG, takes out the low of the previous `N` bars (minor liquidity), and closes back above that low without closing below the IFVG. This is the **BUY** signal, and entry is at that candle's close. |
| 6 | **Targets (draw on liquidity)** | TP1 is the nearest untouched swing high that is at least `Min R` away. TP2 is the next swing high after it. If no swing high qualifies, the target falls back to a fixed R multiple. The stop goes below the retest-sweep low, plus a small ATR buffer. |

A setup is cancelled if price:
- makes a new extreme before all confirmations are in,
- closes back through the far side of the IFVG,
- breaks the original sweep extreme, or
- runs out of time at any step.

Cancelled IFVG boxes turn grey.

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
- **Entry / SL / TP1 · DOL / TP2 · DOL lines:** these follow the trade until it ends. If `Move SL to entry after TP1` is on, the SL moves to break-even once TP1 is hit.
- **Stats table (top right):** number of entries, TP1 and TP2 hit rates, and number of stop-outs. These counts are for the bars loaded on your chart.

## Tuning tips
- **Lower timeframes (1–5m):** use `Liquidity swing length` 3–5 and `Recovery displacement` 1.0–1.5.
- **Higher timeframes:** use `Liquidity swing length` 5–10.
- **Too few signals:** raise `Max bars sweep → CISD & IFVG` or `FVG may form up to N bars before sweep`, or lower `Min FVG size`.
- **Too many signals:** raise `Recovery displacement` or `Min R for TP1 liquidity`.

This is a study tool, not financial advice.
