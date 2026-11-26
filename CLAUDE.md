# CLAUDE.md — ORB trading project (read this first)

This file gives Claude Code the full context of this project, so a new session can carry on without the owner re-explaining anything.
**If the owner says "do the current task", "continue" or "start", go straight to [Current task](#current-task).**

---

## 1. Owner & preferences

- Owner: Ali (GitHub `alikamal94`). Trades **gold (XAUUSD)**, intraday, ICT/SMC style.
- Platforms: **TradingView** (Pine Script v6) for indicators/backtests, **MetaTrader 5 on a Mac** for the EA.
- Prefers **complete, ready-to-paste scripts** over partial diffs. When a script changes, deliver the full file.
- Wants results, not repeated guess-and-check rounds. **Verify with data before handing anything over.**
- Signal colours to keep: **Blue = entry, Red = SL, Green = TP, Purple = breakout**.
- Git: work on branch `claude/charming-lovelace-9v31cy`, commit with clear messages, push.

## 2. The strategy (ORB breakout + retest)

1. **Opening range (ORB):** the high / low / 50% of the first 1, 5 or 15 (or 30) minutes after a session opens.
   Sessions (each in its own time zone, DST-aware):
   - Asia: 09:00 Asia/Tokyo
   - London: 08:00 Europe/London
   - NY Open: 09:30 America/New_York
   - NY Close: 15:00 America/New_York (assumed definition; confirm with the owner if needed)
2. **Breakout:** a candle **closes** beyond the ORB High or ORB Low (50% level optional).
3. **Retest entry:** price comes back to the broken level and the entry is confirmed by any of:
   - a **Fair Value Gap** left by the breakout move (price taps it and closes in the trade direction),
   - a **High/Low level retest** (touches the level within a tolerance, closes back beyond it),
   - a **strong rejection candle** (pin bar with a long wick, or an engulfing candle).
4. **Risk:** SL beyond the retest candles / ORB 50% / opposite ORB side; TP as an R multiple.
   LONG TP must be above entry, SHORT TP below entry.
5. **Non-repainting:** signals only on **closed** candles; drawings anchored by time and never moved.

## 3. Files in this repo

| File | What it is |
|---|---|
| `indicators/orb-ny/ORB_NY.pine` | Original indicator: NY session only, 1/5/15m ORBs, non-repainting fixes. |
| `indicators/orb-ny/ORB_NY_code.pdf` | PDF export of the above. |
| `indicators/orb-sessions/ORB_Sessions.pine` | Indicator for all 4 sessions (Asia, London, NY Open, NY Close). |
| `indicators/orb-sessions/ORB_Sessions_code.pdf` | PDF export of the above. |
| `strategies/orb-sessions/ORB_Sessions_Strategy.pine` | v1 backtest strategy (same rules as the sessions indicator). |
| `strategies/orb-sessions/ORB_Sessions_Pro_Strategy.pine` | v2 "PRO" strategy: trend/size/candle filters, partial TP + break-even. **Current version.** |
| `ea/orb-ny/ORB_NY_EA.mq5` | MT5 Expert Advisor (NY session only) with the same rules. |
| `ea/orb-ny/install-mac.sh`, `install.bat`, `install.ps1` | EA installers for Mac / Windows. |

Lessons learned writing Pine v6 in this project (avoid repeating these compile errors):
- Never break a line right after an opening parenthesis `(`; continuation lines must not be indented by a multiple of 4 spaces.
- Don't put several statements on one line separated by commas.
- Pine functions **cannot reassign global variables**. Keep shared mutable state in a `var` object (UDT) and change its fields.
- Call `table.merge_cells` once (`barstate.isfirst`), not on every bar.

## 4. Backtest history (TradingView Strategy Tester, XAUUSD)

| Version | Trades | Win rate | Profit factor | Net | Max DD | Notes |
|---|---|---|---|---|---|---|
| v1 `ORB_Sessions_Strategy` | 448 | 31.9% | 0.857 | −33.95% | 45.88% | All 4 sessions, 50% breaks on, fixed 2R, tight stops, margin calls. |
| v2 `ORB_Sessions_Pro_Strategy` (defaults) | 23 | 52.2% | 0.711 | −1.45% | 2.98% | London + NY only, filters on, TP1 0.7R + BE runner to 2R. Sample far too small (TradingView only loaded ~1 month of 5m data). |

Both versions **lose money**. The v2 defaults were chosen from research, not fitted to data, so they are unverified.

Research consulted (for context):
- Zarattini & Aziz, *Can Day Trading Really Be Profitable?*: 5-min ORB, small stop, hold to end of day.
- *A Profitable Day Trading Strategy For The U.S. Equity Market*: ORB on "stocks in play", 10% ATR stop.
- MQL5 blog replication on index CFDs: "gross reproduced, net zero". Costs can erase the edge.

## 5. Owner's target

**Win rate 70–80% AND profit factor 1.5–2.0**, out-of-sample, after costs.

Honest constraint: PF ≈ (WR × avg win) / ((1 − WR) × avg loss). At 75% WR, PF 1.5 needs avg win ≈ 0.5 × avg loss, so this only works with small first targets and a real edge. If the data says it isn't achievable, **say so with numbers** and present the best realistic trade-off. Do not overfit to hit the number.

Note: with partial exits, TradingView counts TP1 and the runner as separate trades, which inflates win rate. Report win rate **per signal** as well as per fill.

---

## Current task

**Find, with real data, the best version of this ORB strategy for XAUUSD, then deliver the final Pine script.**

1. **Data:** download ≥ 2 years of XAUUSD 1-minute data, e.g. Dukascopy (`https://datafeed.dukascopy.com/datafeed/XAUUSD/YYYY/MM/DD/HHh_ticks.bi5`; month is 0-based; LZMA-compressed ticks), or any reliable free source. Resample to 5m. Use a realistic spread (≈ $0.20–0.35 for gold) plus commission.
2. **Replicate:** rebuild `strategies/orb-sessions/ORB_Sessions_Pro_Strategy.pine` logic in Python (pandas). Run the v2 defaults and sanity-check the behaviour against the Pine rules.
3. **Search** (grid or random search; keep it structured, not thousands of blind combos):
   - sessions (London, NY Open, both; Asia / NY Close for completeness)
   - ORB length 5 / 15 / 30 min; chart 1m vs 5m
   - entry: retest (limit at level) vs breakout close vs FVG only
   - filters: VWAP, HTF EMA (15m/1H/4H, 20/50/200), range-size vs daily ATR, strong breakout candle, day-of-week
   - stop: ORB 50%, opposite side, retest candle, ATR multiple
   - exits: TP1 0.3–1.0R with 30–80% partial, BE move, TP2 1–3R / session end; fixed small TP (0.5–1R)
4. **Validate:** choose settings on 2023–2024 (in-sample), then test **unchanged** on 2025+ (out-of-sample). Also walk-forward if time allows. Report per signal: trades, win rate, PF, expectancy (R), net %, max DD, longest losing streak.
5. **Deliver:**
   - Update the Pine strategy (and the `ORB_Sessions.pine` indicator) with the winning rules/defaults. Keep the colours and the non-repainting rules.
   - Compile-check the Pine if a compiler is available. Otherwise review against the "lessons learned" above.
   - Write `strategies/orb-sessions/BACKTEST_REPORT.md` with the results table, equity curve image, chosen settings and an honest verdict versus the 70–80% / 1.5–2 target.
   - Commit and push to `claude/charming-lovelace-9v31cy`. Give the owner the **full final script** in chat.
6. **Optional follow-up:** port the final rules to the MT5 EA (`ea/orb-ny/ORB_NY_EA.mq5`) for all sessions.
