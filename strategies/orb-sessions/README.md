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
