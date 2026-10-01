# Supply & Demand Confluence Pro (Pine Script v5)

Script: [`SD_Confluence_Pro.pine`](SD_Confluence_Pro.pine). It's a TradingView strategy that reads zones from a higher timeframe and enters on a lower timeframe. The confirmations are a liquidity sweep, a market structure shift (MSS) with displacement, an RSI check, and the retest of an FVG, iFVG, Unicorn or Order Block.

---

## 1. What was wrong with the original (Google) spec

| # | Problem in the spec | Fix in this script |
|---|---|---|
| 1 | `recalc_on_order_fills` doesn't exist in Pine. The real flag is `calc_on_order_fills`, and turning it on together with `process_orders_on_close` re-runs the bar after a fill. That can double-fire signals and inflate backtests. | `calc_on_order_fills = false`, `process_orders_on_close = true` |
| 2 | "`request.security` with `lookahead_off`" still **repaints in realtime**, because it returns the HTF bar while that bar is still forming. | Uses TradingView's documented pattern: `expr[1]` + `lookahead_on`. Only *closed* HTF bars are used. |
| 3 | No RSI anywhere, even though you wanted RSI. | RSI exhaustion (OS/OB) **or** regular divergence while price is in the zone, plus an optional 50-line momentum check on the MSS candle. |
| 4 | "Risk 1–2% of equity" without a sizing formula. Using `default_qty_type = percent_of_equity` risks *position value*, not *stop distance*. | `qty = equity × risk% ÷ (SL distance × pointvalue × FX rate)` |
| 5 | Ignored currency conversion. On **GBPJPY, USDJPY and GBPNZD** the P&L is in JPY/NZD, so naive sizing comes out ~150× too small on JPY pairs. | `request.currency_rate(syminfo.currency, account currency)` |
| 6 | Default 100% margin blocks FX/NQ positions sized by stop distance. | `margin_long/short = 2` (1:50). Adjust to your broker. |
| 7 | "High volume" doesn't apply to spot FX, which only has tick volume. | Displacement = body/range ratio **and** (body ≥ ATR × k **or** relative volume ≥ k) |
| 8 | No HTF trend bias. The spec would buy demand inside a bearish HTF structure. | HTF bias filter: last HTF break of structure and/or HTF EMA |
| 9 | No check for an opposing zone sitting in front of the target. | "Room to target": rejects the trade if an opposing HTF zone is closer than 1.5R |
| 10 | Zones never expire or get consumed, so the chart clutters up. | Zones are deleted when a candle closes through them. They expire by age and touch count (fresh-zone option), and the chart shows at most N per side. |
| 11 | Killzones on 1H/4H charts make no sense, since one bar spans the whole session. | Killzones apply only below 1H by default |
| 12 | No daily risk brakes. | Max trades per day plus `strategy.risk.max_intraday_loss` |
| 13 | `CADUSD` is not a standard symbol. | Use **USDCAD** (or `FX_IDC:CADUSD` if you really want the inverse) |

---

## 2. Trading rules: the checklist the script enforces

**A. Context (HTF: 1H or 4H)**
1. **Demand zone:** an HTF candle with a big body (≥ 1.2 × ATR, body ≥ 55% of its range) closes above the highest high of the last 10 HTF bars (a break of structure). The **last bearish candle before it** is the Order Block. The zone runs from that candle's high down to the lowest low of the move. Supply is the mirror image.
2. A zone is **only valid until a candle body closes through it**. Fresh zones are best, and by default a zone can be traded on at most 2 touches.
3. Skip zones taller than 2.5 × HTF ATR, because the stop would be too wide.
4. **Bias:** only buy demand when the last HTF break of structure was bullish (optionally also price above the HTF 50 EMA).

**B. Setup (LTF: 5m or 15m)**

5. **Tap:** price wicks into the HTF zone. That "arms" the setup for up to 40 bars.
6. **RSI:** while armed, RSI reaches ≤ 30 (≥ 70 for shorts) **or** prints a regular divergence (a lower low in price with a higher low in RSI).
7. **Liquidity sweep (+1 score):** a wick takes out a minor swing low and the candle **closes back above** it (stop run).

**C. Confirmation**

8. **MSS:** a candle **closes** above the most recent confirmed minor swing high (pivot 3/3).
9. **Displacement:** that candle (or the one before it) has a body ≥ 60% of its range **and** (body ≥ 1 × ATR **or** volume ≥ 1.5 × average).
10. **Killzone:** the MSS must happen inside London (02:00–05:00), NY AM (08:30–11:00) or NY PM (13:30–16:00), New York time.

**D. Entry, ranked by priority**

11. **Unicorn:** a bullish breaker (the last up-candle before the sweep low, now closed above) overlapping a bullish FVG from the up-leg. Gets +2 score.
12. **FVG:** the 3-candle imbalance created by the displacement leg. Gets +1.
13. **iFVG:** a bearish FVG that a candle body closed back above, so it now acts as support. Gets +1.
14. **OB:** the last down-candle in the up-leg (fallback).
15. Place a **limit at the proximal edge** (or the 50% "CE"). Cancel it if it's not filled within 12 bars, if price runs to the target first, or if the killzone ends.

**E. Risk**

16. **SL** goes below the sweep low plus 0.25 × ATR (or below the zone's distal edge, which you can pick in the settings).
17. **Reject** the trade if the SL is < 0.5 × ATR (noise) or > 4 × ATR (too wide).
18. **TP** at 1.5R / 2R / 3R. Move the SL to break-even at +1R (optional).
19. Risk 1% per trade (adjustable). At most 2 trades a day, and trading stops for the day after a 3% loss.

**Confluence score (0–5):** Sweep · RSI zone signal · RSI momentum · FVG/iFVG entry · Unicorn. The default minimum is **2**. Raise it to 3 for fewer, A-grade trades.

---

## 3. Recommended pairings

| Chart (execution) | HTF zones (Auto) | Notes |
|---|---|---|
| 5m | 1H | Most trades. Keep killzones ON. |
| 15m | 4H | The best balance for most pairs and Gold |
| 1H | 4H | Swing-ish. Killzones are auto-disabled. |
| 4H | Daily | Position trades. Raise *Setup expiry*. |

**Per-asset tips**
- **NQ1!:** point value 20, so 1% of $10k usually comes out to < 1 contract. Use a larger capital, set *Quantity step* = 1, or trade **MNQ1!**. NY AM is the main killzone.
- **XAUUSD:** spreads are wide, so set slippage/commission in Properties. Max SL of 3–4 ATR works well.
- **FX majors / crosses:** set *Quantity step* = 1000 (micro lots). For GBP crosses, London plus NY AM is best.

---

## 4. Alerts (webhook JSON)

1. Add the strategy to the chart, then **Create Alert** → Condition: *S&D Pro* → *Order fills only* (or *Order fills and alert() calls* if you enabled setup-armed alerts).
2. Message box: `{{strategy.order.alert_message}}`
3. Payload example (the first 5 keys are always present; the rest come from *extended fields*):

```json
{"action":"buy","ticker":"XAUUSD","price":"2385.40","sl":"2378.90","tp":"2398.40",
 "qty":"12","event":"entry","side":"buy","rr":"2","score":"3","interval":"15","time":"2026-10-01T13:45:00Z"}
```

`event` is one of `entry`, `exit` or `exit_be` (break-even modification).

---

## 5. Before trusting the backtest

- Set **commission and slippage** for each asset in Properties. FX with zero cost always looks better than reality.
- Use **Bar Magnifier** (Premium) so the intrabar SL/TP order gets resolved correctly.
- Test at least 200 trades and use walk-forward testing: tune on one year and validate on the next. Don't optimize every input on the same data.
- Turn on **"Show rejected setups"** to see *why* trades were skipped while tuning.
