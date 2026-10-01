# ORB NY — Opening Range Breakout + Retest (TradingView / Pine v6)

Paste `ORB_NY.pine` into the TradingView Pine Editor → **Add to chart**.

## How it works

1. **Opening range.** At the New York open (09:30 America/New_York by default) the script records the high, low and 50% level of the first **1, 5 and 15 minutes**. Each range is drawn in its own colour and extended until the end of the session.
2. **Breakout.** Using the ORB selected in *ORB used for signals*, it waits for a candle to **close** through the **ORB High**, the **ORB Low**, or the **50% level**. The 50% level only counts while price is still inside the range.
3. **Retest and entry.** Once a level breaks, the script waits for price to come back to it. It confirms the entry with any of the enabled checks:
   - **FVG.** Price comes back into the first Fair Value Gap left by the breakout move and closes in the breakout direction.
   - **High/Low retest.** Price touches the broken level (within the tolerance) and closes back on the breakout side.
   - **Strong rejection candle.** At the level, a pin bar (a long wick with the close in the top or bottom 40%) or an engulfing candle.

The setup is cancelled if price closes back through the level by more than the tolerance, if no retest comes within *Max bars*, or at the signal cut-off time (12:00 ET by default).

## Chart timeframe

An ORB window can only be built from bars that fit inside it:

| Chart | ORBs available |
|-------|----------------|
| 1m    | 1m, 5m, 15m    |
| 5m    | 5m, 15m        |
| 15m   | 15m            |

With *Auto*, the signal ORB matches the chart timeframe. On any other timeframe it uses the 15m ORB.

## Risk and outputs

- **Entry:** the broken ORB level (the FVG edge for FVG entries), or the signal candle's close.
- **Stop loss:** beyond the retest candle (default), at the opposite ORB side (ORB High for shorts, ORB Low for longs), or at ORB 50%, plus an ATR buffer. The stop is always placed on the losing side of the entry.
- **Take profit:** LONG = entry + R × risk (above the entry); SHORT = entry − R × risk (below the entry).
- Colours: blue = entry, red = SL, green = TP, purple = breakout label.
- Info table: the High/50%/Low of each ORB (★ marks the signal ORB) and the live status.
- Alerts: *ORB NY Long* and *ORB NY Short*. You can also create an alert on **Any alert() function call** to get breakout, entry, TP and SL messages with prices.

## Non-repainting

- Signals, labels and lines are only created when a candle has **closed**.
- All drawings are placed by time with fixed end points, so they never move once drawn.
- Each session's drawings are kept in arrays, and only whole old sessions are removed (*Days of drawings to keep*).
- *Max signals per session* (default 1) locks the session once the signal fires. Each level gets only one breakout label per session.
