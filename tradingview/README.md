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

### Signal mode (first setting)
Pick how strict the indicator is. The model stays the same in every mode (sweep → V → CISD → IFVG → retest). Only the filters loosen.

| Setting | Sniper | **Balanced** (default) | Aggressive |
|---|---|---|---|
| Retest confirmation | sweep of minor liquidity | rejection candle (closes in the trade direction) | touch of the IFVG that holds |
| 1H EMA bias | above/below **and** sloping | above/below only | off |
| Killzones (New York time) | 02–05, 07–11 | 01–06, 07–13 | off |
| Liquidity swing length | 8 | 5 | 3 |
| V recovery | 1.5× ATR within 6 bars | 1.2× ATR within 10 bars | 0.9× ATR within 15 bars |
| Bars allowed for sweep → CISD/IFVG / to wait for retest | 12 / 16 | 20 / 24 | 30 / 40 |
| Min body of IFVG candle / min retracement | 50% / 50% | 35% / 25% | off / off |
| Draw on liquidity beyond TP1 | required | required | off |
| Max trades / losses per day | 2 / 1 | 4 / 2 | 8 / 4 |

**Custom** uses your own value for every setting marked with *. In the other modes, the * settings are set by the mode. The table header shows which mode is running.

### High-probability filters (the Sniper settings, tuned for the 15M chart)
- **HTF bias:** longs only when the 1H close is above a rising 50 EMA; shorts only below a falling one. It uses the last closed 1H bar, so it doesn't repaint.
- **Killzones:** entries only during London (02:00–05:00 New York time) and New York (07:00–11:00).
- **Major liquidity only:** swing length is 8, and the previous day's high and low are added as liquidity pools.
- **Displacement:** the candle that inverts the FVG must have a body of at least 50% of its range.
- **Stop size:** a retest is skipped if its stop would be larger than 2× ATR. Stops tighter than 0.3× ATR are widened so normal noise doesn't hit them.
- **Draw on liquidity:** the trade is only taken if there's an untouched liquidity pool at least TP1 away in the trade direction.
- **Discount / premium:** a long is only taken if the entry is at least 50% of the way back down the V leg (from the V high to the sweep low). Shorts mirror this.
- **Asia range:** the Asia session high and low (20:00–00:00 New York time) are added as liquidity, so London sweeps of Asia count.
- **Daily limits:** at most 2 trades a day, and no more trades after the first loss of the day.
- **One position at a time:** a long can't open while a short is running, and the reverse.

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

## Strategy version (real backtest)
`ifvg-sniper-strategy.pine` uses the same signals, but it's a strategy, so TradingView's **Strategy Tester** tab reports results from real orders:
- Each trade risks 1% of equity (you can change this).
- 50% closes at TP1, the stop moves to entry, and the rest closes at TP2.
- The tester reports win rate, profit factor and drawdown, with your own commission and slippage settings.

Add it the same way as the indicator (Pine Editor → new script → paste → Save → Add to chart), then open **Strategy Tester** below the chart. Alerts with named conditions are only in the indicator version.

## Chart legend
Each setup is labelled with its steps, in order:
- **1 Sweep:** where the liquidity was taken. A dashed line runs from the swing that was swept.
- **2 V:** the V-shape recovery.
- **3 CISD:** the line price closed through.
- **4 IFVG:** the shaded box. This is the zone to wait for.
- **5 BUY / SELL:** the confirmed entry after the retest sweep. Hover over it to see entry, SL, TP1, TP2, retracement and the draw on liquidity.

After the entry, the trade is drawn like TradingView's position tool:
- **Red box:** the risk (entry to SL).
- **Green box:** the reward (entry to TP2).
- **Dashed line:** TP1.

When TP1 is hit, the red box greys out and the SL label moves to entry. Each outcome is labelled with its result in R: **✓ TP1**, **✓ TP2 +1.5R**, **BE +0.5R**, **✕ SL -1R**, or **Time exit**.

To keep the chart clean:
- Cancelled setups are removed. Turn on *Keep cancelled setups on chart* to see them in grey.
- Liquidity lines are hidden by default. Turn on *Show resting liquidity levels* to show them.
- *Label size* changes the size of all labels, and the stats table can sit in any corner.

**Stats table:** closed trades, win rate (R > 0), TP1 and TP2 hit rates, stops before TP1, net R and average R per trade, for the bars loaded on your chart. Below them it shows live status: the HTF bias, whether a killzone is open, today's trades and losses, and what each side is waiting for.

## Tuning tips
Check **Win rate** and **Avg R** in the stats table on the 15M chart with about 2–3 months of history loaded, then:
- **Win rate too low:** turn on `Move SL to entry after TP1` if it's off, raise `Min body %` to 0.6, raise `Liquidity swing length` to 10, or narrow the killzones.
- **Too few trades:** turn off `Require draw on liquidity beyond TP1`, raise `Skip entry if stop > N × ATR` to 2.5, or turn off the HTF filter.
- **Want more R per trade:** set `Close % at TP1` to 0 (then TP1 only moves the stop to break-even) or raise TP2.

This is a study tool, not financial advice.
