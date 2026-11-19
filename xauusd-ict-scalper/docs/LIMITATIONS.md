# Verification status, TradingView limitations, known issues

## Verification status — read this first

| Item | Status |
|---|---|
| Pine scripts compile in TradingView | **NOT VERIFIED.** TradingView's compiler could not be reached from the build environment, and no offline Pine v6 compiler exists. The scripts were written against the v6 reference and desk-checked line by line, and an open-source grammar parser was run on them (all statements parse; details in the project README). That is not a compile. Expect to fix a small number of compiler errors when you first paste them; send the error text and line number and they can be corrected quickly. |
| Pine results match the Python engine | **NOT VERIFIED**, for the same reason. The logic was ported definition by definition with identical defaults, but no TradingView Strategy Tester run exists. |
| Python backtest results | **Verified** — produced by running `research/run_report.py`; reproducible. |
| Backend webhook server | **Verified** locally (store, duplicate rejection, auth, statistics). |
| 2023 data | **Not tested** — unavailable. |

## TradingView limitations that shape the design

- **No persistent memory.** A script is recalculated from the first loaded bar on every reload, input change or
  alert creation. The adaptive engine's state is a pure function of the loaded history, so it is reproducible, but
  it "forgets" anything older than the loaded bars and differs between accounts with different history depth.
- **Intraday history depth.** A 3-minute chart loads roughly 5k–40k bars depending on plan (about 2–16 weeks of
  gold). A 2023–2025 backtest on 3M needs **Deep Backtesting** (Premium and above). Without it the Strategy
  Tester covers only recent weeks — far too few trades to mean anything.
- **Bar Magnifier** (`use_bar_magnifier=true`) needs Premium. Without it TradingView guesses the intrabar path,
  which matters for a strategy whose stop and target can sit inside one bar.
- **No historical spread.** Pine cannot see bid/ask on historical bars, so a real spread filter is impossible.
  The strategy models spread *cost* through commission (cash per contract = half the spread per side). It does
  not model that short stops are triggered by the ask; "Pad short stops by the spread" is the workaround.
- **Realtime bid/ask** is not available on minute charts either; the "excessive spread" condition is therefore
  not implemented in Pine. The Python engine has it (`max_spread_usd`).
- **Non-multiple timeframes.** A 5M request from a 3M chart is allowed, but the two grids only line up every
  15 minutes; the script always takes the last 5M bar that had closed by the chart bar's close.
- **Alerts** fire once per bar close. `alert()` messages are dynamic JSON; `alertcondition()` exists only in the
  indicator (TradingView ignores it in strategies) and its text is static.
- **Contract size.** On OANDA:XAUUSD one unit is one ounce. The strategy sizes in ounces and rounds down to the
  broker's lot step using the "contract size" input (default 100 oz per lot). Check Tauro Markets' symbol
  specification — if their lot is not 100 oz, change the input or the lot sizes shown will be wrong.
- **Session days.** The daily reset uses the chart's daily bar boundary (17:00 New York on OANDA).

## Known issues and unsupported features

- **One position at a time is fixed, not optional.** Reversing or stacking positions is not supported.
- **"Excessive spread" filter** — Python only (see above).
- **Stop/target are computed from the signal bar's close**, the fill happens at the next open. Realized
  risk/reward therefore differs slightly from the planned value.
- **Breakeven and trailing update once per bar** (at the close) in Pine; the Python engine applies breakeven at
  1-minute resolution. Trailing, partial close, the volatility-scaled stop buffer, the FVG-origin stop and the
  news blackout are implemented but were tested only in Python (trailing, partial, breakeven, FVG-origin) or not
  at all (volatility-scaled buffer, short-stop padding, news blackout).
- **Indicator vs strategy results differ slightly by design**: the indicator simulates outcomes on chart bars
  and assumes the stop is hit first when stop and target share a bar; the strategy uses the broker emulator.
- **Equal highs/lows** are detected between swing pivots only, not between arbitrary wicks.
- **Pivot ties**: Pine's `ta.pivothigh` and the Python pivot can disagree when two bars share an identical
  extreme. Rare on a 3-decimal gold feed.
- **Dashboard and drawings** are limited to TradingView's 500 labels/lines; older markers disappear.
- **The score is not predictive** on tested data (see the report). A default minimum of 75 gives very few trades.
