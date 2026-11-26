# ORB Sessions Strategy (backtest version)

This is the [ORB Sessions indicator](../../indicators/orb-sessions/) turned into a TradingView `strategy()`, so the **Strategy Tester** can measure it. The signal rules are identical. The differences:

- **Real orders.** It places strategy orders for every signal: a limit order at the retest level (or a market order at the signal close), with the SL and the 2R TP attached.
- **One position at a time.** A real account can only be net long or short, so a signal from another session while a trade is open is skipped and labelled *"signal skipped (in trade)"*.
- **Time exits.** Unfilled limit orders are cancelled after *N* bars. Open trades are closed when the session's level window ends.

## How to backtest

1. Open the **Pine Editor**, paste `ORB_Sessions_Strategy.pine`, then click **Save** and **Add to chart**.
2. Pick your symbol (e.g. XAUUSD) and a **1m or 5m** chart.
3. Open the **Strategy Tester** tab under the chart. It shows the Overview (net profit, drawdown, equity curve), Performance Summary, and List of Trades.
4. In the strategy settings, set:
   - **Inputs → Backtest:** start/end date, risk % per trade (default 1%) or a fixed quantity, and the limit-order expiry.
   - **Properties:** initial capital, **commission** and **slippage**. Both are 0 by default; set them to match your broker, or the results will look better than reality.

## Limits to keep in mind

- **History depth:** on 1m/5m charts, TradingView only loads a limited number of bars (it depends on your plan). For a longer test, use the 5m or 15m chart, or **Deep Backtesting** on Premium plans.
- **Fills inside a candle:** the tester only sees OHLC data. If SL and TP are both hit inside the same candle, it has to assume an order. Turn on *Bar Magnifier* (Properties, paid plans) for more realistic fills.
- **Bar Replay:** use it as well to watch each signal form candle by candle.

---

# ORB Sessions PRO Strategy (v2)

`ORB_Sessions_Pro_Strategy.pine` is the refined version, written after the first backtest (32% win rate, profit factor 0.86, margin calls).

| Problem in v1 | Fix in PRO |
|---|---|
| Too many low-quality trades (448) | Asia and NY Close are off by default. 50% breakouts are off. Only the **first** breakout per session counts. Max 1 trade per session and 2 per day. |
| Traded against the trend | **Trend filter**: longs only above session VWAP **and** the 1H EMA 50, shorts only below both. |
| Noise days and exhausted days | **Range-size filter**: the opening range must be 0.10–0.60 × the 14-day daily ATR. |
| Weak breakouts | The breakout candle must close beyond the level with a body ≥ 50% of the candle. |
| Tiny stops hit by noise (and oversized positions) | Stop at the **ORB 50%** level by default, at least 0.5 × ATR away. Trades whose stop is wider than 0.5 × daily ATR are skipped. |
| Fixed 2R target with a 32% win rate | **TP1 at 0.7R (50% of the position)**. The stop then moves to break-even, and the runner aims for **2R** or the session end. |
| Margin calls | Risk % sizing capped at **20× leverage**. |

Every rule above can be turned off or tuned in the settings, so each one can be tested on its own.

## Testing method

1. Run it on XAUUSD **5m** with the defaults, and set commission/slippage under Properties.
2. Change **one** thing at a time (trend filter, TP1 R, stop mode, entry type, sessions) and note the win rate, profit factor and drawdown.
3. Pick settings on one period (e.g. 2025), then check them **unchanged** on a different period. If the results collapse, the settings were overfitted.

## About win rate vs profit factor

Profit factor ≈ (win rate × average win) ÷ ((1 − win rate) × average loss). A 75% win rate with PF 1.5 needs the average win to be about **0.5 × the average loss**, so high-win-rate settings use small first targets. With partial exits, the Strategy Tester counts TP1 and the runner as separate trades, which raises the displayed win rate. Judge the strategy on **net profit, profit factor and drawdown**, not win rate alone.
