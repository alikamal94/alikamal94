# XAUUSD ICT Adaptive Scalping System

A non-repainting ICT scalping system for gold (OANDA:XAUUSD, 3-minute and 5-minute charts) in TradingView Pine
Script v6, with a rule-based adaptive filter engine, a Python research engine that backtests it on real bid/ask
tick data, and an optional backend for persistent statistics.

## Honest status

| | |
|---|---|
| **Backtest result** | **No demonstrated edge. The profit-factor ≥ 2.0 target was not met.** Best meaningful result: 3M baseline, PF 1.09 in development (2024–2025) and PF 1.03 out-of-sample (2026), neither statistically different from zero. 5M was negative. Full detail: [docs/BACKTEST_REPORT.md](docs/BACKTEST_REPORT.md). |
| **Pine compilation** | **Not verified in TradingView.** The compiler was not reachable from the build environment. See the syntax-check result below and [docs/LIMITATIONS.md](docs/LIMITATIONS.md). |
| **Data** | 2024-01 → 2026-11 (Dukascopy ticks). **2023 was not available** and was not tested. |
| **Use** | Research and demo forward-testing. Not validated for live trading. |

## Deliverables

| # | Deliverable | Where |
|---|---|---|
| 1 | Pine v6 indicator | [pine/XAUUSD_ICT_Adaptive_Indicator.pine](pine/XAUUSD_ICT_Adaptive_Indicator.pine) |
| 2 | Pine v6 strategy / backtesting version | [pine/XAUUSD_ICT_Adaptive_Strategy.pine](pine/XAUUSD_ICT_Adaptive_Strategy.pine) |
| 3 | Adaptive engine | in both scripts; design in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) |
| 4 | Alert system | in both scripts; setup in [docs/FORWARD_TESTING.md](docs/FORWARD_TESTING.md) |
| 5 | Dashboard | in both scripts |
| 6 | Full list of settings | [docs/SETTINGS.md](docs/SETTINGS.md) |
| 7 | Installation instructions | [docs/FORWARD_TESTING.md](docs/FORWARD_TESTING.md) |
| 8 | Recommended initial settings | end of [docs/SETTINGS.md](docs/SETTINGS.md) |
| 9 | Backtesting report with actual results | [docs/BACKTEST_REPORT.md](docs/BACKTEST_REPORT.md), raw output in [research/results/](research/results/) |
| 10 | TradingView limitations | [docs/LIMITATIONS.md](docs/LIMITATIONS.md) |
| 11 | Known bugs / unsupported features | [docs/LIMITATIONS.md](docs/LIMITATIONS.md) |
| 12 | Forward-testing instructions | [docs/FORWARD_TESTING.md](docs/FORWARD_TESTING.md) |
| + | Persistent-learning backend: plan and working server | [docs/PYTHON_BACKEND.md](docs/PYTHON_BACKEND.md), [backend/webhook_server.py](backend/webhook_server.py) |

## What the system does

Liquidity sweep → displacement → market structure shift → fair value gap → retrace → confirmation candle, scored
0–100, filtered by session, multi-timeframe bias, volatility and stop distance, sized at 0.5 % risk with a
structural stop beyond the sweep extreme and a 1:3 target. Daily limits on trades, loss and losing streaks. A
deterministic adaptive controller tightens the filters after poor rolling results and relaxes them back to — never
below — the baseline. Details: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Headline numbers (0.5 % risk per trade, real bid/ask spread, zero commission)

| Mode | Period | Trades | Win rate | Profit factor | Expectancy | t-stat | Net | Max drawdown |
|---|---|---|---|---|---|---|---|---|
| 3M baseline | 2024–2025 (development) | 284 | 33.8 % | 1.09 | +0.058 R | 0.60 | +7.6 % | −8.6 % |
| 3M baseline | 2026 (out-of-sample) | 121 | 28.9 % | 1.03 | +0.020 R | 0.13 | +0.8 % | −10.6 % |
| 5M baseline | 2024–2025 (development) | 206 | 30.1 % | 0.78 | −0.158 R | −1.57 | −15.5 % | −21.1 % |
| 5M baseline | 2026 (out-of-sample) | 76 | 26.3 % | 0.71 | −0.206 R | −1.26 | −7.7 % | −8.6 % |
| 3M default (score ≥ 75) | 2024–2025 | 66 | 28.8 % | 0.81 | −0.141 R | −0.74 | −4.7 % | −11.7 % |
| 3M default (score ≥ 75) | 2026 | 28 | 35.7 % | 1.15 | +0.095 R | 0.30 | +1.2 % | −3.9 % |

"Baseline" is the ICT sequence with no score or bias gate — the largest sample. A |t-stat| below 2 means the
result cannot be distinguished from no edge; under 100 trades is inconclusive.

## Pine syntax check

SYNTAX_CHECK_RESULT

## Repository layout

```
pine/       the two deliverable scripts, the shared template they are generated from, build + syntax tools
research/   tick -> bar builder, backtest engine, report generator, results (tables, trade lists, chart)
backend/    optional webhook server for persistent statistics
docs/       architecture, settings, backtest report, limitations, forward testing, backend plan
```

Nothing here is financial advice. Leveraged gold trading can lose more than you expect, quickly.
