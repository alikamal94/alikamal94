# Watchlist and thresholds
Used by: Market Intelligence (1). The threshold check is plain code, not AI.

```watchlist
XAUUSD | 1.0 | 4
EURUSD | 0.5 | 4
GBPUSD | 0.5 | 4
USDJPY | 0.5 | 4
US30   | 1.0 | 4
NAS100 | 1.2 | 4
USOIL  | 2.0 | 4
BTCUSD | 3.0 | 4
```
Format: `symbol | move % that counts as big | lookback hours`. Gold ±1% in 4 hours is from the build spec; the others are starting guesses for Ali to tune.
