"""Runs every experiment quoted in docs/BACKTEST_REPORT.md and writes
research/results/report_tables.md plus trade lists and an equity chart.

Usage: XAU_BARS=<path>/xauusd_m1.parquet python run_report.py
"""
import os, sys
import numpy as np, pandas as pd
import ict_engine as E, common as C

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
os.makedirs(OUT, exist_ok=True)
L = []
KEYS = ["trades", "win_rate", "pf", "exp_r", "t_stat", "net_r", "net_pct", "max_dd_pct",
        "avg_win_r", "avg_loss_r", "max_consec_loss", "avg_mfe_r", "avg_mae_r"]


def md(df):
    cols = list(df.columns)
    out = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for _, r in df.iterrows():
        out.append("| " + " | ".join("" if (isinstance(v, float) and np.isnan(v)) else str(v) for v in r) + " |")
    return "\n".join(out)


def verdict(s):
    if s.get("trades", 0) < 100:
        return "inconclusive (n<100)"
    if abs(s["t_stat"]) < 2:
        return "not significant"
    return "positive" if s["t_stat"] > 0 else "negative"


def srow(name, t):
    s = E.stats(t)
    r = {"config": name}
    r.update({k: s.get(k, 0) for k in KEYS})
    r["verdict"] = verdict(s) if s.get("trades", 0) else "no trades"
    return r


CONFIGS = {
    "Baseline ICT (sequence only)": dict(min_score=0, htf_req=0),
    "Baseline + Adaptive": dict(min_score=0, htf_req=0, ad_on=1),
    "Moderate (score>=65, 1 HTF)": dict(min_score=65, htf_req=1),
    "Moderate + Adaptive": dict(min_score=65, htf_req=1, ad_on=1),
    "Default (score>=75, 2 HTF)": dict(),
    "Default + Adaptive": dict(ad_on=1),
    "Strict (75, 2 HTF, 1H/4H veto, graded liquidity, OB)": dict(htf_veto=2, min_liq_w=0.5, ob_required=1),
}

data = {tf: C.load(tf) for tf in (3, 5)}
runs = {}
for tf, D in data.items():
    for name, ov in CONFIGS.items():
        runs[(tf, name)] = E.run(D, **ov)

L.append("## 1. Strategy comparison\n")
for label, per in (("Development 2024-01-01 .. 2025-12-31", C.DEV), ("Out-of-sample 2026-01-01 .. 2026-11-15", C.OOS)):
    for tf in (3, 5):
        rows = [srow(name, E.split(runs[(tf, name)], *per)) for name in CONFIGS]
        L.append(f"### {label} - {tf}M execution\n\n" + md(pd.DataFrame(rows)) + "\n")

# ---- breakdowns on the widest sample (baseline, no score gate) ----
L.append("## 2. Breakdowns (Baseline ICT, no score gate - largest sample)\n")
for tf in (3, 5):
    t = runs[(tf, "Baseline ICT (sequence only)")].copy()
    t["period"] = np.where(t["entry_time"] < pd.Timestamp(C.OOS[0], tz="UTC"), "DEV", "OOS")
    t["weekday"] = t["entry_time"].dt.tz_convert(E.NY).dt.day_name()
    t["session"] = t["sess"].map({1.0: "London", 2.0: "New York"})
    t["score_bucket"] = pd.cut(t["score"], [0, 60, 65, 70, 75, 80, 100]).astype(str)
    t["exit"] = t["exit_reason"].map({1.0: "stop", 2.0: "target", 3.0: "breakeven", 4.0: "time/EOD", 5.0: "trail"})
    t["liquidity"] = t["kind"].astype(int).map(E.KIND_NAMES)
    t["year"] = t["entry_time"].dt.year
    for col in ("session", "weekday", "score_bucket", "liquidity", "exit", "year"):
        g = t.groupby(["period", col], observed=True)["R"].agg(
            n="count", win_rate=lambda r: round((r > 0).mean() * 100, 1), exp_r=lambda r: round(r.mean(), 3),
            net_r=lambda r: round(r.sum(), 1)).reset_index()
        L.append(f"### {tf}M by {col}\n\n" + md(g) + "\n")
    dev = t[t.period == "DEV"]
    rho = dev[["score", "R"]].corr(method="spearman").iloc[0, 1]
    L.append(f"{tf}M score calibration (DEV): Spearman correlation between score and trade R = {rho:.3f} (n={len(dev)}).\n")
    t.drop(columns=["period"]).to_csv(os.path.join(OUT, f"trades_baseline_{tf}m.csv"), index=False)
    runs[(tf, "Default (score>=75, 2 HTF)")].to_csv(os.path.join(OUT, f"trades_default_{tf}m.csv"), index=False)
    L.append(f"{tf}M signals rejected by filter (Default config, whole sample): `{runs[(tf, 'Default (score>=75, 2 HTF)')].attrs['rej']}`\n")

# ---- cost sensitivity ----
L.append("## 3. Cost sensitivity (Baseline ICT, 3M, development period)\n")
rows = []
for nm, ov in (("zero spread (gross)", dict(spread_mult=0)), ("0.5x recorded spread", dict(spread_mult=0.5)),
               ("1.0x recorded spread", dict()), ("1.5x recorded spread", dict(spread_mult=1.5)),
               ("1.0x spread + $0.10 slippage/side", dict(slip_usd=0.10))):
    rows.append(srow(nm, E.split(E.run(data[3], min_score=0, htf_req=0, **ov), *C.DEV)))
L.append(md(pd.DataFrame(rows)) + "\n")
m1 = pd.read_parquet(C.BARS, columns=["spr"])
q = m1["spr"].groupby(m1.index.year).agg(["mean", "median", lambda s: s.quantile(0.95)]).round(3)
q.columns = ["mean", "median", "p95"]
L.append("Recorded Dukascopy spread (USD/oz) by year:\n\n" + md(q.reset_index().rename(columns={"ts": "year"})) + "\n")

# ---- exit-management variants ----
L.append("## 4. Risk/reward and trade-management variants (Baseline ICT, 3M)\n")
rows = []
for nm, ov in (("RR 1:1", dict(rr=1)), ("RR 1:1.5", dict(rr=1.5)), ("RR 1:2", dict(rr=2)), ("RR 1:3 (default)", dict()),
               ("RR 1:4", dict(rr=4)), ("RR 1:3 + breakeven at 1R", dict(be_on=1)),
               ("RR 1:3 + 50% partial at 1R + breakeven", dict(part_on=1, be_on=1)),
               ("RR 1:3 + ATR trail from 1.5R", dict(trail_on=1)),
               ("Opposing-liquidity target", dict(tp_mode=1))):
    t = E.run(data[3], min_score=0, htf_req=0, **ov)
    a = srow(nm, E.split(t, *C.DEV)); b = E.stats(E.split(t, *C.OOS))
    a["OOS trades"] = b.get("trades", 0); a["OOS exp_r"] = b.get("exp_r", 0); a["OOS pf"] = b.get("pf", 0)
    rows.append(a)
L.append(md(pd.DataFrame(rows).drop(columns=["verdict", "avg_mfe_r", "avg_mae_r"])) + "\n")

# ---- walk-forward ----
L.append("## 5. Walk-forward validation (3M and 5M)\n")
GRID = [dict(min_score=ms, htf_req=hr, rr=rr) for ms in (0, 65, 75) for hr in (0, 2) for rr in (2.0, 3.0)]
for tf in (3, 5):
    gruns = [E.run(data[tf], **g) for g in GRID]
    rows = []; picked = []
    start = pd.Timestamp("2024-01-01", tz="UTC")
    while True:
        tr0 = start; tr1 = start + pd.DateOffset(months=6); te1 = tr1 + pd.DateOffset(months=3)
        if tr1 >= pd.Timestamp("2026-11-15", tz="UTC"):
            break
        best = None; best_t = 0.0
        for gi, t in enumerate(gruns):
            s = E.stats(t[(t.entry_time >= tr0) & (t.entry_time < tr1)])
            if s.get("trades", 0) >= 25 and s["exp_r"] > 0 and s["t_stat"] > best_t:
                best = gi; best_t = s["t_stat"]
        if best is None:
            rows.append(dict(train=f"{tr0.date()}..{tr1.date()}", test=f"{tr1.date()}..{te1.date()}",
                             chosen="none (no config with positive train expectancy) -> stand aside",
                             train_t=np.nan, test_trades=0, test_exp_r=np.nan, test_net_r=0.0))
        else:
            tt = gruns[best]; te = tt[(tt.entry_time >= tr1) & (tt.entry_time < te1)]
            te = te.copy(); te.attrs = {}
            picked.append(te)
            rows.append(dict(train=f"{tr0.date()}..{tr1.date()}", test=f"{tr1.date()}..{te1.date()}",
                             chosen=str(GRID[best]), train_t=round(best_t, 2), test_trades=len(te),
                             test_exp_r=round(te.R.mean(), 3) if len(te) else np.nan,
                             test_net_r=round(te.R.sum(), 1)))
        start = start + pd.DateOffset(months=3)
    L.append(f"### {tf}M - 6-month train / 3-month test, rolled every 3 months, 12 candidate configs, "
             "selection by train t-statistic (not net profit)\n\n" + md(pd.DataFrame(rows)) + "\n")
    allp = pd.concat(picked).sort_values("entry_time") if picked else pd.DataFrame(columns=E.TCOLS)
    fixed = runs[(tf, "Baseline ICT (sequence only)")]
    fixed = fixed[fixed.entry_time >= pd.Timestamp("2024-07-01", tz="UTC")]
    L.append(md(pd.DataFrame([srow("Walk-forward selected (all test windows stitched)", allp),
                              srow("Fixed Baseline over the same test span", fixed)])) + "\n")

# ---- adaptive engine activity ----
L.append("## 6. Adaptive engine activity\n")
for tf in (3, 5):
    for nm in ("Baseline + Adaptive", "Moderate + Adaptive", "Default + Adaptive"):
        t = runs[(tf, nm)]; ad = t.attrs["ad_log"]
        lv = t.groupby("ad_level")["R"].agg(n="count", exp_r=lambda r: round(r.mean(), 3)).reset_index()
        L.append(f"{tf}M {nm}: {len(ad)} filter changes over {len(t)} trades; trades by adaptive level at entry: "
                 + "; ".join(f"L{int(r.ad_level)} n={int(r.n)} exp={r.exp_r}R" for r in lv.itertuples()) + "\n")

# ---- equity chart ----
try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(1, 2, figsize=(13, 4.2), sharey=True)
    for a, tf in zip(ax, (3, 5)):
        for nm in ("Baseline ICT (sequence only)", "Baseline + Adaptive", "Default (score>=75, 2 HTF)"):
            t = runs[(tf, nm)]
            a.plot(t.exit_time, t.R.cumsum(), label=nm, lw=1.3)
        a.axvline(pd.Timestamp(C.OOS[0], tz="UTC"), color="grey", ls="--", lw=1)
        a.set_title(f"{tf}M execution - cumulative R (dashed line = start of out-of-sample)")
        a.axhline(0, color="black", lw=0.6); a.grid(alpha=0.3); a.legend(fontsize=8)
    ax[0].set_ylabel("cumulative R (1R = 0.5% risk)")
    fig.tight_layout(); fig.savefig(os.path.join(OUT, "equity_curves.png"), dpi=130)
except Exception as ex:
    print("chart skipped:", ex)

open(os.path.join(OUT, "report_tables.md"), "w").write("\n".join(L))
print("\n".join(L))
