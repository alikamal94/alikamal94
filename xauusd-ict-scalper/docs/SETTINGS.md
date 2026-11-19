# Settings

> **Shipped defaults changed on request (more frequent signals):** baseline minimum score 0 (was 75), min aligned
> timeframes 0 (was 2), adaptive engine off (was on). In the Python test on 3M this is about 2.7 trades a week
> instead of 0.6. The tables below still list the original values; set them back in the inputs to restore them.

All inputs exist in both scripts unless marked. Defaults are the values the brief asked for; where the brief was
silent they are conventional ICT values, not optimised ones.

## 1 – Liquidity
| Input | Default | Meaning |
|---|---|---|
| Internal swing length | 5 | Pivot length for short-term swing highs/lows (internal liquidity). |
| External swing length | 20 | Pivot length for major swings (external liquidity). |
| Equal high/low tolerance (ATR) | 0.10 | Two swings closer than this form equal highs/lows. |
| Swing pool max age (bars) | 300 | Swing pools older than this are dropped. |
| HTF/session/day pool max age (bars) | 1500 | Same for 1H / 4H / session / day pools. |
| Minimum liquidity grade | 0.35 | Pools below this grade cannot start a setup. 0.35 internal swing · 0.55 prev 1H · 0.65 external swing · 0.80 equal H/L and prev 4H · 0.90 prev session · 1.00 prev day. |
| Bars allowed to reclaim a pierced level | 2 | 0 = the sweep candle itself must close back across the level. |
| Internal swings / External swings / Prev 1H / Prev 4H / Prev session / Prev day | on | Which pools are tracked. |

## 2 – Displacement and structure
| Input | Default | Meaning |
|---|---|---|
| Min displacement body (ATR) | 1.0 | Candle body relative to ATR(14). |
| Min body / range | 0.60 | Body-to-range ratio. |
| Min range vs 10-bar average range | 1.20 | Relative expansion. |
| Max close distance from candle extreme | 0.30 | Directional close: closes in the outer 30 % of its range. |
| Structure pivot length (MSS) | 3 | Pivot length of the swing that must be broken. |
| Max bars from sweep to MSS | 30 | Setup expires after this. |

## 3 – Fair value gap and order block
| Input | Default | Meaning |
|---|---|---|
| Min FVG size (ATR) | 0.15 | Minimum gap size / quality. |
| Max FVG age (bars) | 30 | The gap must be retested within this many bars. |
| Bars after MSS in which the FVG may complete | 2 | A gap needs a third candle, which may come after the MSS bar. |
| Required retrace depth into FVG | 0.0 | Partial mitigation rule: 0 = touch the edge, 0.5 = reach the midpoint. |
| Full mitigation (invalidation) rule | Close through gap | Or "Wick through gap". |
| Confirmation candle must close beyond FVG midpoint | on | |
| Order block lookback | 5 | Bars searched before the displacement for the last opposing candle. |
| Require order block confluence | off | Off = order block only adds 5 score points. |

## 4 – Multi-timeframe bias
| Input | Default | Meaning |
|---|---|---|
| Bias EMA fast / slow | 20 / 50 | A timeframe is bullish when close > slow EMA and fast > slow (bearish mirrored). |
| 5M / 15M / 1H / 4H | on | Timeframes that take part. |
| Min aligned timeframes | 2 | Set 0 to disable the bias filter. |
| Opposition veto | None | Optionally reject when 1H (or 1H and 4H) points the other way. |

## 5 – Stop loss and take profit
| Input | Default | Meaning |
|---|---|---|
| Structural stop anchor | Sweep extreme | Or "FVG origin candles" (tested: worse). |
| Stop buffer (ATR) | 0.10 | Added beyond the anchor. |
| Scale buffer with volatility regime | off | Untested option. |
| Min / Max stop distance (ATR) | 0.6 / 3.5 | Trades outside are rejected — the stop is never moved to make a trade fit. |
| Min / Max stop distance (USD) | 0 / 0 (off) | Absolute bounds. |
| Risk / reward | 1:3 | 1:1, 1:1.5, 1:2, 1:3, 1:4 or Custom. |
| Target mode | Fixed R multiple | Or nearest opposing liquidity between the min and max R. |
| Min room to opposing liquidity (R) | 0 (off) | Reject when the nearest opposing pool is closer than this. |
| Partial close | off | Close a percentage at a given R. |
| Breakeven | off | Move stop to entry (plus offset) after a given R. |
| ATR trailing stop | off | Starts after a given R. |
| Max bars in trade | 0 (off) | Time stop. |

## 6 – Risk management
| Input | Default | Meaning |
|---|---|---|
| Risk per trade (% of equity) | 0.5 | Never changed by the adaptive engine. |
| Max trades per day | 5 | |
| Max daily loss (%) | 1.5 | No new entries for the rest of the day. |
| Daily profit lock (%) | 0 (off) | |
| Max consecutive losses per day | 3 | |
| Cooldown between entries (bars) | 5 | |
| Broker contract size (oz per 1.00 lot) | 100 | **Verify with Tauro Markets.** |
| Lot step / Min lot / Max lots | 0.01 / 0.01 / 50 | Size is rounded down; a trade smaller than the minimum lot is skipped. |
| Assumed spread (USD per oz) | 0.30 | Indicator: cost of virtual trades. Strategy: only for short-stop padding. |
| Pad short stops by the spread | off | |
| Account equity for lot sizing | 10 000 | Indicator only. |

Strategy **Properties** tab (not inputs): initial capital 10 000 USD, commission 0.15 USD per contract (models a
$0.30 spread — set it to half of your real spread), slippage in ticks, Bar Magnifier on.

## 7 – Sessions and filters
| Input | Default | Meaning |
|---|---|---|
| Trade sessions | Both | Both / London only / New York only. |
| London session | 07:00–11:00 Europe/London | Daylight saving handled by the timezone. |
| New York session | 08:00–12:00 America/New_York | |
| London / New York kill zone | 07:00–10:00 / 08:30–11:00 | Only affects the session score. |
| Flatten / stop trading at (New York) | 16:50 | Avoids the daily rollover spread. |
| Volatility filter | on, 0.6–2.5 | ATR(14) relative to its 200-bar average. |
| Manual news blackout | off | Two New York-time windows. |

## 8 – Signal score
Weights 20 / 20 / 15 / 15 / 15 / 5 / 10 (sweep, displacement, MSS, FVG, HTF, order block, session) and the
baseline minimum score, default 75.

## 9 – Adaptive engine
Enable (default on in Pine), min sample 20, window 20, tighten below 0 R, relax above +0.25 R, max level 4,
5 trades between changes, steps of 3 score / 0.05 ATR displacement / 0.02 ATR FVG, idle decay 10 days, bucket
rule 12 trades / −0.15 R / 5 points.

## 10 – Visuals and alerts
Dashboard on/off, compact mode and position; signal labels; entry/SL/TP lines; FVG box; exit markers; previous
day high/low; dynamic `alert()` messages on/off.

---

# Recommended initial settings for OANDA:XAUUSD

These are starting points for **demo forward testing**, chosen for sample size and robustness, not because they
were the most profitable in the backtest (nothing was significantly profitable).

| Setting | Recommendation | Why |
|---|---|---|
| Chart | OANDA:XAUUSD, 3 minutes | 3M was the less bad of the two modes; 5M was negative in both periods. |
| Baseline minimum score | **65** for evaluation (75 is the shipped default) | 75 gives ~30 trades a year, which can never be evaluated. The score has no measured predictive value, so a lower gate costs nothing and gives a sample. |
| Min aligned timeframes | 1 | Same reason. |
| Risk / reward | 1:3, fixed | The brief's default; no alternative tested better out-of-sample. |
| Partial / breakeven / trailing | off | They raised win rate and lowered expectancy. |
| Risk per trade | 0.5 % or less | Losing runs of 11 occurred. |
| Sessions | Both | No stable difference between London and New York. |
| Commission (Properties) | half of your measured Tauro spread | The result is highly cost-sensitive. |
| Adaptive engine | on | Harmless: it can only tighten above the baseline. Do not expect it to add return. |
