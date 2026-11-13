# ORB NY EA — MetaTrader 5 Expert Advisor

This EA trades the same strategy as the [ORB NY TradingView indicator](../../indicators/orb-ny/).

1. **Opening range.** It builds the New York opening range (09:30 NY) over 1, 5 or 15 minutes from M1 data.
2. **Breakout.** It waits for a candle to **close** through the ORB High, ORB Low or 50% level.
3. **Retest entry.** It enters on the retest once a **Fair Value Gap**, a **High/Low level retest** or a **strong rejection candle** (pin bar or engulfing) confirms it.

Signals are only checked on **closed** candles of the signal timeframe.

## Install

**Quick way (Windows):** put `ORB_NY_EA.mq5`, `install.bat` and `install.ps1` in one folder and double-click `install.bat`. It copies the EA into MT5 and compiles it. Then go to step 3 below.

**Manual way:**

1. In MT5 go to **File → Open Data Folder → MQL5 → Experts** and copy `ORB_NY_EA.mq5` there.
2. Open it in **MetaEditor** and press **Compile** (F7).
3. Drag **ORB_NY_EA** onto a chart (for example XAUUSD) and turn on **Algo Trading**.

## Important: broker time zone

MT5 runs on the broker's server clock, so the EA needs to know where 09:30 New York falls:

| Your broker | Setting |
|---|---|
| Most FX / gold brokers (server GMT+2 in winter, GMT+3 in summer) | *Broker follows NY close*, offset **7** (the default) |
| Server on a fixed GMT+N with no daylight saving | *Broker is fixed GMT+N*, then set the broker's GMT offset |

To check: at 09:30 New York time, your MT5 Market Watch clock should read 16:30 (offset 7).

## Main settings

| Group | Setting | Default |
|---|---|---|
| Opening range | Signal timeframe / ORB length | M5 / Auto (= 5 min) |
| Breakout | High/Low breakouts, 50% breakouts, retest tolerance, max bars to wait | on, on, 0.25 × ATR, 30 |
| Confirmation | FVG, level retest, rejection candle | all on |
| Risk | Entry type | Market at the confirmation close (or a limit order at the level) |
| Risk | Stop loss | Beyond the retest candles + 0.1 × ATR (or opposite ORB side / ORB 50%) |
| Risk | Take profit | 2R: LONG = entry + 2 × risk, SHORT = entry − 2 × risk |
| Risk | Position size | 1% of equity per trade (or fixed lots) |
| Risk | Break-even, max spread | off, off |
| Session | Max trades per session, stop new signals, close trades | 1, 12:00 NY, 16:00 NY |

## Backtest first

Use the **Strategy Tester** (Ctrl+R), modelling **Every tick based on real ticks** (or *1 minute OHLC*), with the same timeframe as *Signal timeframe*. Run it on a demo account before going live. Note that a pending limit order can fill at a different price than in the tester when the market moves fast.

## Notes

- Only one trade is open at a time. Each trade is tagged with the magic number, so the EA leaves your manual trades alone.
- If the EA restarts mid-session, it picks up its open position or order but forgets a setup that was still waiting for a retest.
