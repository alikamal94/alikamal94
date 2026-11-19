# Optional backend for persistent learning

Pine Script cannot remember anything between executions, so the in-chart adaptive engine only knows the trades
visible in the loaded history. If you want statistics and the adaptive level to survive reloads, cover your whole
forward test, or combine several charts, they have to live outside TradingView. This is separate from the core
scripts and entirely optional.

## Architecture

```
TradingView alert()  --HTTPS webhook-->  reverse proxy (TLS)  -->  webhook_server.py  -->  SQLite
                                                                        |
                                              GET /stats  <-------------+   rolling stats + suggested level
```

- **Ingest**: the scripts already emit JSON for BUY/SELL, ENTRY_FILLED, EXIT, DAILY_LOSS_LIMIT,
  MAX_DAILY_TRADES and ADAPTIVE_CHANGED. Point one "Any alert() function call" alert at the webhook URL.
- **Store**: `events` (every message, de-duplicated on event + symbol + bar time) and `trades` (one row per
  signal, completed by its EXIT message).
- **Compute**: `/stats` returns 10/20/30/50-trade win rate, profit factor and expectancy, and replays the same
  deterministic level rule the Pine script uses over the *entire* stored history.
- **Feed back**: TradingView has no inbound API, so the backend cannot push settings into a chart. The loop is
  closed manually — read the suggested level and raise "Baseline minimum score" by 3 points per level — or by
  moving order execution to the backend (below).

## What exists now

`backend/webhook_server.py` — standard library only, tested locally: stores messages, rejects duplicates and
bad tokens, pairs exits with signals, serves statistics.

```bash
python backend/webhook_server.py --db trades.sqlite --port 8080 --token <long random string>
# TradingView webhook URL:  https://your-domain/tv?token=<same string>
# Statistics:               https://your-domain/stats?token=<same string>
```

TradingView webhooks need a paid plan with 2FA enabled, a public HTTPS endpoint on port 443, and they time out
after about 3 seconds. Run the server behind Caddy or nginx; never expose it without the token.

## Implementation plan for a fuller system

| Phase | Work | Notes |
|---|---|---|
| 1 | Deploy the server on a small VPS behind TLS; back up the SQLite file daily. | Done in an afternoon. |
| 2 | Record **real fills**: add a broker-side logger (MT5 Python API or the broker's REST API) that writes actual entry/exit prices and spread next to each alerted trade. | Gives true slippage — the number the backtest is most sensitive to. |
| 3 | Move the adaptive decision server-side: the backend decides whether an incoming signal passes the current level and bucket penalties, and only then forwards it (Telegram / order router). | This is the only way to have genuinely persistent adaptation. Pine then runs with the baseline filters. |
| 4 | Weekly report job: rolling statistics, score calibration, comparison with the backtest ranges. | Catches deterioration early. |
| 5 | Optional: Postgres instead of SQLite, authentication beyond a URL token, IP allow-listing of TradingView's webhook addresses. | Only if it becomes more than a personal tool. |

Keep the same guarantees as the in-chart engine: never loosen below the baseline, never raise risk after losses,
never touch stops, require a minimum sample before any change, and change one step at a time.
