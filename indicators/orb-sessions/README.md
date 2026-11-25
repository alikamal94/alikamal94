# ORB Sessions — Asia / London / NY Open / NY Close (TradingView, Pine v6)

This indicator applies the ORB NY breakout-and-retest strategy to **four sessions**. Each session has its own opening range, state, signals and trade, so overlapping sessions don't interfere with each other.

| Session | Default open | Time zone | New signals for | Levels / trades until |
|---|---|---|---|---|
| Asia | 09:00 | Asia/Tokyo | 3 h | 6 h after open |
| London | 08:00 | Europe/London | 3 h | 5 h after open |
| NY Open | 09:30 | America/New_York | 2 h 30 (until 12:00) | 16:00 |
| NY Close | 15:00 | America/New_York | 1 h | 17:00 |

Each session's times are set in its own time zone, so daylight saving is handled automatically. All times, durations, colours and on/off switches can be changed in the settings.

## Rules (same for every session)

1. **Opening range:** the high, low and 50% of the first 1/5/15 minutes after the session opens (*Auto* matches the chart timeframe).
2. **Breakout:** a candle **closes** through the ORB High, the ORB Low or the 50% level.
3. **Retest entry:** confirmed by a **Fair Value Gap**, a **High/Low level retest** or a **strong rejection candle** (pin bar or engulfing).
4. **Risk:** the SL is beyond the retest candles, at the opposite ORB side or at ORB 50%. The TP is **2R**: above the entry for longs, below it for shorts.
5. **One signal per session** by default. The session then locks until its next open.

## Non-repainting

Signals and drawings are only created on **closed** candles and are anchored by time, so they never move once drawn.

## Display

- Each session's range uses its own colour: Asia amber, London blue, NY Open purple, NY Close teal.
- Signal colours: blue = entry, red = SL, green = TP, purple = breakout.
- Labels name the session (e.g. *LONG · London*).
- The info table shows High / 50% / Low and the live status of every session.

## Alerts

- *ORB Sessions Long* and *ORB Sessions Short*.
- **Any alert() function call** gives detailed breakout, entry, TP and SL messages that include the session name.

## Chart timeframe

| Chart | ORB lengths available |
|---|---|
| 1m | 1, 5, 15 |
| 5m | 5, 15 |
| 15m | 15 |
