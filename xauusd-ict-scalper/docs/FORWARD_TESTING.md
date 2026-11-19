# Installation and forward testing

## Installation

1. Open TradingView → chart **OANDA:XAUUSD** → timeframe **3 minutes** (or 5 minutes for the 5M mode).
2. Open the **Pine Editor**, create a new blank script, delete its contents.
3. Paste the full text of `pine/XAUUSD_ICT_Adaptive_Strategy.pine`, press **Save**, then **Add to chart**.
4. If the editor reports a compile error, note the line number and message (see "verification status" in
   [LIMITATIONS.md](LIMITATIONS.md) — the scripts could not be compiled before delivery).
5. Repeat with `pine/XAUUSD_ICT_Adaptive_Indicator.pine` if you want signals and alerts without the Strategy Tester.
   Run one or the other on a chart, not both.
6. Strategy → **Settings → Properties**: set initial capital to your account size, commission to *half your real
   spread in USD per ounce* (cash per contract), slippage to taste, and tick **Bar Magnifier** if your plan has it.
7. Inputs → "Broker contract size": confirm against the XAUUSD specification in your Tauro Markets terminal.

## Reproducing the backtest in TradingView

- Strategy Tester → enable **Deep Backtesting** (Premium or higher) and set the range. Without it a 3M chart only
  covers the last few weeks.
- Compare trade count, win rate and average trade with [BACKTEST_REPORT.md](BACKTEST_REPORT.md). Expect
  differences: TradingView uses OANDA prices and a constant spread model, the report uses Dukascopy bid/ask.
  A large disagreement in *trade count* would indicate a porting error worth reporting.

## Alerts

- **Strategy or indicator, full details:** create one alert, condition = the script, option **"Any alert()
  function call"**, trigger "Once per bar close". Messages are JSON containing symbol, timeframe, direction,
  entry, stop loss, take profit, risk/reward, score, session, lots and adaptive level.
- **Indicator, simple alerts:** the alert dialog also lists BUY signal, SELL signal, Trade entry, Stop loss hit,
  Take profit hit, Daily loss limit reached, Maximum daily trades reached and Adaptive filter changed.
- Recreate alerts after changing any input: an alert keeps the settings it was created with.

## Forward-test protocol

The backtest found no significant edge, so forward testing is the experiment that decides whether to continue —
not a formality before going live.

1. **Demo account only**, same broker and account type you would trade (so spread and execution are real).
2. **Freeze the settings** before you start and write them down. Changing settings mid-test restarts the test.
3. **Take every signal** exactly as alerted: entry at market on the alert, the stop and target from the message,
   the lot size from the message. Skipped trades invalidate the sample.
4. **Log for each trade**: alert time, alerted entry / SL / TP, your actual fill, spread at entry, exit price,
   result in R. The difference between alerted and actual fill is your real slippage.
5. **Minimum sample: 100 completed trades.** At 3–4 trades a week that is several months. Fewer is inconclusive.
6. **Stop conditions** — end the test and do not go live if, after 100 trades, expectancy is ≤ 0 R, or if
   drawdown exceeds 15 R at any point, or if average real slippage plus spread exceeds 0.15 R per trade.
7. **Continue condition** — expectancy clearly above zero (t-statistic ≥ 2, i.e. mean R ÷ (standard deviation of
   R ÷ √n)) *and* live results inside the backtest's range. Even then start at a fraction of 0.5 % risk.
8. Review weekly; compare the dashboard's rolling statistics with your own log. If they disagree, trust your log.

## Rebuilding and re-running the research

```bash
pip install numpy pandas numba pyarrow matplotlib
python research/build_bars.py <dir with Dukascopy tick repos> bars     # ticks -> 1-minute bid/ask bars
XAU_BARS=bars/xauusd_m1.parquet python research/run_report.py          # all tables + chart
python pine/build.py                                                   # regenerate both Pine scripts
```

Tick data used: `Touhid-HZ/xauusd-tick-data-2024`, `-2025`, `-2026` on GitHub (Dukascopy feed, MIT licence).
The raw data is not committed here (about 2.4 GB).
