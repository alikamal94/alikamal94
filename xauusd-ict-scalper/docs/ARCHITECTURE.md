# Architecture and signal logic

## Components

| Layer | File | Role |
|---|---|---|
| Shared Pine source | `pine/src/ict_adaptive.template.pine` | One source for all logic. `pine/build.py` generates the two scripts from it, so indicator and strategy cannot drift apart. |
| Strategy | `pine/XAUUSD_ICT_Adaptive_Strategy.pine` | Places orders through TradingView's broker emulator; statistics come from real `strategy.closedtrades`. |
| Indicator | `pine/XAUUSD_ICT_Adaptive_Indicator.pine` | Same signals, alerts and dashboard; trade outcomes are simulated bar by bar as "virtual trades". |
| Research engine | `research/ict_engine.py` | Python twin of the logic, run on tick-derived bid/ask data. Source of every number in the report. |
| Optional backend | `backend/webhook_server.py` | Stores alerts in SQLite so statistics persist across chart reloads. |

## Timeframe model

The chart timeframe is the execution timeframe. Put the script on a **3-minute** chart for 3M execution or a
**5-minute** chart for 5M execution; these are two independently testable modes, as the brief asked for when exact
cross-timeframe execution is not possible. On a 3M chart the 5M bias is one of the confirmation inputs. Pine cannot
honestly execute on 3M bars from a 5M chart (it would have to guess the path inside the bar), so that is not attempted.

Higher timeframes (5M, 15M, 1H, 4H, D) come from five `request.security()` calls with `lookahead_off`. Only the
last **closed** higher-timeframe bar is used, on historical and realtime bars alike, so nothing repaints.

## Entry sequence (bullish case; bearish is the exact mirror)

Internally shorts are processed on mirrored prices (price × −1), so one state machine serves both directions.

1. **Liquidity pools** are registered below price: internal swing lows, external swing lows, equal lows (two
   distinct swings within the tolerance), previous 1H low, previous 4H low, previous session low (Asia / London /
   New York on the New York clock) and previous day low. Each has a grade from 0.35 (internal swing) to 1.00
   (previous day). Pools expire with age.
2. **Sweep** — a bar trades below a pool and a candle closes back above it (the same bar, or within "bars allowed
   to reclaim"). A close that stays below means the level was broken, not swept, and the pool is discarded. The
   lowest price of the sweep is recorded for the stop. Pools below the minimum grade cannot start a setup.
3. **Displacement** — after the sweep, a candle whose body is ≥ 1.0 ATR, body/range ≥ 0.6, range ≥ 1.2× the
   10-bar average and which closes in the top 30 % of its range. The last down-close candle before it is stored
   as the **order block**.
4. **Market structure shift** — a close above the most recent confirmed short-term swing high that existed when
   the sweep happened. Requires a displacement candle in the leg. Must occur within 30 bars of the sweep.
5. **Fair value gap** — `low > high[2]`, at least 0.15 ATR, created in the leg after the sweep (or up to two bars
   after the MSS). The most recent qualifying gap is used.
6. **Retrace** — price trades back into the gap. The setup dies if a candle closes through the gap (full
   mitigation), if price trades below the sweep low, or if the gap is older than 30 bars.
7. **Confirmation** — a bullish candle that closes above the gap midpoint after the retrace.
8. **Filters** — session, end-of-day window, news blackout, volatility band, stop distance bounds, HTF alignment,
   optional order-block requirement, optional room-to-liquidity, minimum score, daily trade count, daily loss,
   profit lock, consecutive losses, cooldown, existing position.
9. **Order** — market entry on the next bar's open. Stop below the sweep low minus an ATR buffer. Target at
   1:3 by default. Each setup can fire at most once.

## Score (0–100)

| Component | Default weight | How it is graded |
|---|---|---|
| Liquidity sweep | 20 | 60 % pool grade (+0.1 per extra pool swept in the same move), 40 % strength of the close back above the level |
| Displacement | 20 | half the points for meeting the minimum, full points at minimum + 1 ATR of body |
| MSS | 15 | 60 % for the break, the rest for closing up to 0.5 ATR beyond the level |
| FVG | 15 | half for meeting the minimum size, full at minimum + 0.5 ATR |
| HTF alignment | 15 | share of enabled timeframes whose bias agrees |
| Order block | 5 | all or nothing: gap overlaps or sits directly on the order block |
| Session | 10 | kill zone = full, rest of session = 60 % |

The score was tested for calibration and **does not predict trade results** on the available data (see the report).
It is a description of how textbook a setup looks, not a probability.

## Adaptive engine

A deterministic controller with one integer state, the tightening level `L` (0 … max, default 4):

- After every completed trade, once at least 20 trades exist, the expectancy of the last 20 trades is computed.
- Expectancy below 0 R → `L + 1`. Expectancy above +0.25 R → `L − 1`. At most one change per 5 trades.
- `L` raises the requirements: minimum score +3 per level, displacement +0.05 ATR per level, FVG +0.02 ATR per
  level, and one extra aligned timeframe from level 2.
- **Condition buckets**: over the last 50 trades, results are grouped by session, order block yes/no, strong HTF
  alignment yes/no and HTF-level vs swing liquidity. A bucket with ≥ 12 trades and expectancy below −0.15 R costs
  setups of that type 5 extra score points.
- **Idle decay**: every 10 trading days without a completed trade the level drops by one. Without this, tightened
  filters can block the very trades needed to relax them (this deadlock was observed in testing and fixed).

Guarantees: thresholds never fall below the configured baseline; position risk never changes; stops are never
widened; past trades are never altered; the same bars always produce the same state. It keeps rolling 10/20/30/50
windows, win rate, profit factor, average R, longest losing run and average MFE/MAE.

It is not machine learning and has no memory beyond the bars loaded on the chart. See
[PYTHON_BACKEND.md](PYTHON_BACKEND.md) for persistence.
