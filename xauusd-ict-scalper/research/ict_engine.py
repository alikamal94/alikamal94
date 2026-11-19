"""XAUUSD ICT Adaptive Scalping System - reference backtest engine.

This is the research twin of the Pine Script strategy in ../pine. The signal
logic (liquidity pools -> sweep -> displacement -> MSS -> FVG -> retrace ->
confirmation), the scoring model, the risk rules and the rule-based adaptive
engine are implemented with the same definitions and default parameters.

Differences from TradingView's broker emulator (all in the conservative
direction):
  * signals are computed on BID bars (what the chart shows), fills use the real
    Dukascopy bid/ask: longs buy the ask and exit on the bid, shorts sell the
    bid and exit on the ask;
  * intrabar order resolution uses 1-minute bars (the same idea as Bar
    Magnifier); if stop and target are both inside one 1-minute bar the stop is
    assumed to be hit first.
"""
import numpy as np
import pandas as pd
from numba import njit

NY = "America/New_York"
LDN = "Europe/London"

# --------------------------------------------------------------------------
# Parameters (defaults mirror the Pine inputs)
# --------------------------------------------------------------------------
DEFAULTS = dict(
    # structure / liquidity
    struct_len=3,          # pivot length for MSS structure
    swing_len=5,           # internal liquidity pivots
    ext_len=20,            # external liquidity pivots
    eq_tol_atr=0.10,       # equal high/low tolerance (ATR)
    liq_max_age=300,       # bars a swing pool stays active
    htf_liq_max_age=1500,  # bars an HTF/session/day pool stays active
    min_liq_w=0.35,        # minimum pool grade to start a setup
    reclaim_bars=2,        # bars allowed to close back across a pierced level
    use_int=1, use_ext=1, use_1h=1, use_4h=1, use_sess=1, use_day=1,
    # displacement
    disp_min_atr=1.0, disp_body_ratio=0.60, disp_exp_mult=1.20, disp_close_pos=0.30,
    # setup timing
    setup_max_bars=30,     # sweep -> MSS deadline
    fvg_min_atr=0.15, fvg_max_age=30, fvg_wait=2,
    fvg_depth=0.0,         # 0 = touch of the gap edge, 0.5 = consequent encroachment
    mitig_mode=0,          # 0 = close through the gap invalidates, 1 = wick through
    confirm_mid=1,         # confirmation candle must close beyond the gap midpoint
    # order block
    ob_lookback=5, ob_required=0,
    # HTF bias
    htf_mask=15,           # bit0=5m bit1=15m bit2=1h bit3=4h
    htf_req=2,             # minimum number of aligned timeframes
    htf_veto=0,            # 0 none, 1 = 1H must not oppose, 2 = 1H and 4H must not oppose
    # stops / targets
    sl_buf_atr=0.10, min_stop_atr=0.6, max_stop_atr=3.5, max_stop_usd=0.0, min_stop_usd=0.0,
    rr=3.0, min_room_r=0.0, tp_mode=0, min_target_r=1.5, max_target_r=5.0,
    part_on=0, part_r=1.0, part_frac=0.5,
    be_on=0, be_r=1.0, be_off_r=0.0,
    trail_on=0, trail_start_r=1.5, trail_atr=2.0,
    max_hold_bars=0,
    # risk
    risk_pct=0.5, max_trades_day=5, max_daily_loss=1.5, daily_profit_lock=0.0,
    max_consec_loss=3, one_pos=1, cooldown_bars=5,
    # filters
    sess_mode=0,           # 0 both, 1 London only, 2 New York only
    vol_min=0.6, vol_max=2.5, max_spread_usd=0.0,
    slip_usd=0.0,          # extra adverse slippage per side on market/stop fills
    spread_mult=1.0,       # scales the recorded spread (cost sensitivity tests)
    # scoring
    w_sweep=20, w_disp=20, w_mss=15, w_fvg=15, w_htf=15, w_ob=5, w_sess=10,
    min_score=75,
    # adaptive engine
    ad_on=0, ad_min_sample=20, ad_window=20, ad_step_score=3, ad_max_level=4,
    ad_cooldown=5, ad_tighten_exp=0.0, ad_relax_exp=0.25, ad_step_disp=0.05,
    ad_step_fvg=0.02, ad_bucket_n=12, ad_bucket_exp=-0.15, ad_bucket_pen=5,
    sl_mode=0,             # 0 = beyond the sweep extreme, 1 = beyond the FVG origin candles
    ad_idle_days=10,       # relax one level after this many trading days without a completed trade
)
PKEYS = list(DEFAULTS.keys())
PI = {k: i for i, k in enumerate(PKEYS)}

TCOLS = ["sig_bar", "dir", "entry_m1", "exit_m1", "entry", "sl", "tp", "exit", "R", "score",
         "sweep_q", "disp", "mss_margin", "fvg_atr", "htf_cnt", "ob", "sess", "kz", "kind",
         "stop_atr", "mfe_r", "mae_r", "ad_level", "exit_reason", "stop_usd", "spread",
         "min_score_eff"]
KIND_W = np.array([0.0, 0.35, 0.65, 0.80, 0.55, 0.80, 0.90, 1.00])
KIND_NAMES = {1: "internal swing", 2: "external swing", 3: "equal H/L", 4: "prev 1H",
              5: "prev 4H", 6: "prev session", 7: "prev day"}
REJ_NAMES = ["session", "htf", "score", "stop_min", "stop_max", "room", "day_trades", "day_loss",
             "consec", "cooldown", "in_position", "volatility", "spread", "ob_required", "eod",
             "profit_lock"]


def make_params(**over):
    p = dict(DEFAULTS)
    for k, v in over.items():
        if k not in p:
            raise KeyError(k)
        p[k] = v
    return np.array([float(p[k]) for k in PKEYS])


# --------------------------------------------------------------------------
# Data preparation
# --------------------------------------------------------------------------
def _rma(x, n):
    out = np.full(len(x), np.nan)
    if len(x) < n:
        return out
    out[n - 1] = np.nanmean(x[:n])
    a = 1.0 / n
    for i in range(n, len(x)):
        out[i] = out[i - 1] + a * (x[i] - out[i - 1])
    return out


def _local_minutes(idx, tz):
    loc = idx.tz_convert(tz)
    return (loc.hour * 60 + loc.minute).to_numpy()


def _in_window(mins, start, end):
    if start <= end:
        return (mins >= start) & (mins < end)
    return (mins >= start) | (mins < end)


def _htf_frame(m1, minutes):
    """Bid OHLC of a higher timeframe with TradingView-like alignment."""
    if minutes >= 1440:
        ny = m1.index.tz_convert(NY)
        key = (ny + pd.Timedelta(hours=7)).normalize().tz_localize(None)   # 17:00 NY roll
        g = m1.groupby(key)
        df = pd.DataFrame({"h": g["bh"].max(), "l": g["bl"].min(), "c": g["bc"].last()})
        close_local = (df.index - pd.Timedelta(hours=7) + pd.Timedelta(days=1))
        df["close_time"] = close_local.tz_localize(NY, ambiguous="NaT", nonexistent="NaT").tz_convert("UTC")
        return df.dropna(subset=["close_time"])
    if minutes == 240:
        ny = m1.index.tz_convert(NY).tz_localize(None)
        key = (ny - pd.Timedelta(hours=1)).floor("240min") + pd.Timedelta(hours=1)
        g = m1.groupby(key)
        df = pd.DataFrame({"h": g["bh"].max(), "l": g["bl"].min(), "c": g["bc"].last()})
        close_local = df.index + pd.Timedelta(minutes=240)
        df["close_time"] = close_local.tz_localize(NY, ambiguous="NaT", nonexistent="shift_forward").tz_convert("UTC")
        return df.dropna(subset=["close_time"])
    key = m1.index.floor(f"{minutes}min")
    g = m1.groupby(key)
    df = pd.DataFrame({"h": g["bh"].max(), "l": g["bl"].min(), "c": g["bc"].last()})
    df["close_time"] = df.index + pd.Timedelta(minutes=minutes)
    return df


def _bias(close, fast=20, slow=50):
    ef = pd.Series(close).ewm(span=fast, adjust=False).mean().to_numpy()
    es = pd.Series(close).ewm(span=slow, adjust=False).mean().to_numpy()
    b = np.zeros(len(close), dtype=np.int8)
    b[(close > es) & (ef > es)] = 1
    b[(close < es) & (ef < es)] = -1
    b[:slow] = 0
    return b


def prepare(m1, tf=3, ldn=("07:00", "11:00"), nyw=("08:00", "12:00"),
            ldn_kz=("07:00", "10:00"), ny_kz=("08:30", "11:00"), ema_fast=20, ema_slow=50):
    """Build every array the core loop needs for a chart timeframe of `tf` minutes."""
    def hm(s):
        a, b = s.split(":")
        return int(a) * 60 + int(b)

    key = m1.index.floor(f"{tf}min")
    g = m1.groupby(key)
    bars = pd.DataFrame({"o": g["bo"].first(), "h": g["bh"].max(), "l": g["bl"].min(),
                         "c": g["bc"].last(), "spr": g["spr"].last()})
    pos = np.arange(len(m1))
    grp = pd.Series(pos, index=key).groupby(level=0)
    bars["ms"] = grp.first()
    bars["me"] = grp.last() + 1
    idx = bars.index
    o, h, l, c = (bars[k].to_numpy() for k in "ohlc")
    pc = np.roll(c, 1); pc[0] = c[0]
    tr = np.maximum(h - l, np.maximum(np.abs(h - pc), np.abs(l - pc)))
    atr = _rma(tr, 14)
    atr_sma = pd.Series(atr).rolling(200).mean().to_numpy()
    atrr = atr / atr_sma
    avgr = pd.Series(h - l).rolling(10).mean().shift(1).to_numpy()

    ny_min = _local_minutes(idx, NY)
    ld_min = _local_minutes(idx, LDN)
    in_ldn = _in_window(ld_min, hm(ldn[0]), hm(ldn[1]))
    in_ny = _in_window(ny_min, hm(nyw[0]), hm(nyw[1]))
    sess = np.where(in_ny, 2, np.where(in_ldn, 1, 0)).astype(np.int8)
    kz = (_in_window(ld_min, hm(ldn_kz[0]), hm(ldn_kz[1])) & in_ldn) | \
         (_in_window(ny_min, hm(ny_kz[0]), hm(ny_kz[1])) & in_ny)
    # liquidity sessions (New York clock): Asia 18:00-03:00, London 03:00-08:00, NY 08:00-17:00
    lsess = np.where(_in_window(ny_min, 18 * 60, 3 * 60), 1,
             np.where(_in_window(ny_min, 3 * 60, 8 * 60), 2,
              np.where(_in_window(ny_min, 8 * 60, 17 * 60), 3, 0))).astype(np.int8)
    eod = _in_window(ny_min, 16 * 60 + 50, 18 * 60)
    ny_idx = idx.tz_convert(NY)
    day = ((ny_idx + pd.Timedelta(hours=7)).normalize().tz_localize(None)
           - pd.Timestamp("2000-01-01")).days.to_numpy().astype(np.int64)

    close_t = pd.DataFrame({"tc": (idx + pd.Timedelta(minutes=tf)).as_unit("ns")})
    out = {}
    for name, mins in (("5", 5), ("15", 15), ("60", 60), ("240", 240), ("D", 1440)):
        hf = _htf_frame(m1, mins).sort_values("close_time")
        hf["b"] = _bias(hf["c"].to_numpy(), ema_fast, ema_slow)
        hf["close_time"] = pd.DatetimeIndex(hf["close_time"]).as_unit("ns")
        mg = pd.merge_asof(close_t, hf[["close_time", "h", "l", "b"]], left_on="tc",
                           right_on="close_time", direction="backward")
        out[name] = mg
    b5 = out["5"]["b"].fillna(0).to_numpy().astype(np.int8)
    b15 = out["15"]["b"].fillna(0).to_numpy().astype(np.int8)
    b60 = out["60"]["b"].fillna(0).to_numpy().astype(np.int8)
    b240 = out["240"]["b"].fillna(0).to_numpy().astype(np.int8)
    lv = np.column_stack([out["60"]["h"], out["60"]["l"], out["240"]["h"], out["240"]["l"],
                          out["D"]["h"], out["D"]["l"]]).astype(np.float64)

    return dict(
        idx=idx, tf=tf, o=o, h=h, l=l, c=c, atr=atr, atrr=atrr, avgr=avgr,
        ms=bars["ms"].to_numpy().astype(np.int64), me=bars["me"].to_numpy().astype(np.int64),
        sess=sess, kz=kz.astype(np.int8), lsess=lsess, eod=eod.astype(np.int8), day=day,
        b5=b5, b15=b15, b60=b60, b240=b240, lv=np.ascontiguousarray(lv),
        spr=bars["spr"].to_numpy(),
        m_bo=m1["bo"].to_numpy(), m_bh=m1["bh"].to_numpy(), m_bl=m1["bl"].to_numpy(),
        m_bc=m1["bc"].to_numpy(), m_ao=m1["ao"].to_numpy(), m_ah=m1["ah"].to_numpy(),
        m_al=m1["al"].to_numpy(), m_ac=m1["ac"].to_numpy(), m_idx=m1.index,
    )


# --------------------------------------------------------------------------
# Core loop
# --------------------------------------------------------------------------
@njit(cache=True)
def _pivot_low(x, i, n):
    """x[i-n] is a pivot low confirmed on bar i (strict vs right side)."""
    j = i - n
    if j - n < 0:
        return False
    v = x[j]
    for k in range(j + 1, i + 1):
        if x[k] <= v:
            return False
    for k in range(j - n, j):
        if x[k] < v:
            return False
    return True


@njit(cache=True)
def _pivot_high(x, i, n):
    j = i - n
    if j - n < 0:
        return False
    v = x[j]
    for k in range(j + 1, i + 1):
        if x[k] >= v:
            return False
    for k in range(j - n, j):
        if x[k] > v:
            return False
    return True


@njit(cache=True)
def _add_level(pool, price, kind, born, tol, KW):
    """Insert a liquidity level (mirrored space: levels sit BELOW price)."""
    cap = pool.shape[0]
    free = -1
    for q in range(cap):
        if pool[q, 5] == 0.0:
            if free < 0:
                free = q
            continue
        if abs(pool[q, 0] - price) <= tol:
            ok = int(pool[q, 1])
            if price == pool[q, 0] or kind > 3 or ok > 3:
                if KW[kind] > KW[ok]:
                    pool[q, 1] = kind
            else:
                pool[q, 1] = 3.0              # two distinct swings at one price: equal lows
            if price < pool[q, 0]:
                pool[q, 0] = price
            return
    if free < 0:                               # full: replace the oldest
        oldest = 0
        for q in range(1, cap):
            if pool[q, 2] < pool[oldest, 2]:
                oldest = q
        free = oldest
    pool[free, 0] = price
    pool[free, 1] = kind
    pool[free, 2] = born
    pool[free, 3] = -1.0
    pool[free, 4] = price
    pool[free, 5] = 1.0


@njit(cache=True)
def run_core(o, h, l, c, atr, atrr, avgr, ms, me, sess, kz, lsess, eod, day,
             b5, b15, b60, b240, lv, spr,
             m_bo, m_bh, m_bl, m_bc, m_ao, m_ah, m_al, m_ac, P, PIDX):
    n = len(c)
    KW = np.array([0.0, 0.35, 0.65, 0.80, 0.55, 0.80, 0.90, 1.00])

    struct_len = int(P[PIDX[0]]); swing_len = int(P[PIDX[1]]); ext_len = int(P[PIDX[2]])
    eq_tol = P[PIDX[3]]; liq_age = P[PIDX[4]]; hliq_age = P[PIDX[5]]; min_liq_w = P[PIDX[6]]
    reclaim = int(P[PIDX[7]])
    use_int = P[PIDX[8]] > 0; use_ext = P[PIDX[9]] > 0; use_1h = P[PIDX[10]] > 0
    use_4h = P[PIDX[11]] > 0; use_sess = P[PIDX[12]] > 0; use_day = P[PIDX[13]] > 0
    disp_min0 = P[PIDX[14]]; disp_body = P[PIDX[15]]; disp_exp = P[PIDX[16]]; disp_cp = P[PIDX[17]]
    setup_max = int(P[PIDX[18]]); fvg_min0 = P[PIDX[19]]; fvg_age = int(P[PIDX[20]])
    fvg_wait = int(P[PIDX[21]]); fvg_depth = P[PIDX[22]]; mitig_mode = int(P[PIDX[23]])
    confirm_mid = P[PIDX[24]] > 0; ob_look = int(P[PIDX[25]]); ob_req = P[PIDX[26]] > 0
    htf_mask = int(P[PIDX[27]]); htf_req0 = int(P[PIDX[28]]); htf_veto = int(P[PIDX[29]])
    sl_buf = P[PIDX[30]]; min_stop = P[PIDX[31]]; max_stop = P[PIDX[32]]
    max_stop_usd = P[PIDX[33]]; min_stop_usd = P[PIDX[34]]
    rr = P[PIDX[35]]; min_room = P[PIDX[36]]; tp_mode = int(P[PIDX[37]])
    min_tgt = P[PIDX[38]]; max_tgt = P[PIDX[39]]
    part_on = P[PIDX[40]] > 0; part_r = P[PIDX[41]]; part_frac = P[PIDX[42]]
    be_on = P[PIDX[43]] > 0; be_r = P[PIDX[44]]; be_off = P[PIDX[45]]
    trail_on = P[PIDX[46]] > 0; trail_start = P[PIDX[47]]; trail_atr = P[PIDX[48]]
    max_hold = int(P[PIDX[49]])
    risk_pct = P[PIDX[50]]; max_tr_day = int(P[PIDX[51]]); max_dloss = P[PIDX[52]]
    profit_lock = P[PIDX[53]]; max_consec = int(P[PIDX[54]]); one_pos = P[PIDX[55]] > 0
    cooldown = int(P[PIDX[56]]); sess_mode = int(P[PIDX[57]])
    vol_min = P[PIDX[58]]; vol_max = P[PIDX[59]]; max_spread = P[PIDX[60]]
    slip = P[PIDX[61]]; spread_mult = P[PIDX[62]]
    w_sweep = P[PIDX[63]]; w_disp = P[PIDX[64]]; w_mss = P[PIDX[65]]; w_fvg = P[PIDX[66]]
    w_htf = P[PIDX[67]]; w_ob = P[PIDX[68]]; w_sess = P[PIDX[69]]; min_score0 = P[PIDX[70]]
    ad_on = P[PIDX[71]] > 0; ad_min_n = int(P[PIDX[72]]); ad_win = int(P[PIDX[73]])
    ad_step = P[PIDX[74]]; ad_max = int(P[PIDX[75]]); ad_cd = int(P[PIDX[76]])
    ad_tight = P[PIDX[77]]; ad_relax = P[PIDX[78]]; ad_sdisp = P[PIDX[79]]; ad_sfvg = P[PIDX[80]]
    ad_bn = int(P[PIDX[81]]); ad_bexp = P[PIDX[82]]; ad_bpen = P[PIDX[83]]
    sl_mode = int(P[PIDX[84]]); ad_idle = int(P[PIDX[85]])

    n_htf = 0
    for bit in range(4):
        if (htf_mask >> bit) & 1:
            n_htf += 1

    MAXT = 60000
    T = np.zeros((MAXT, 27))
    nt = 0
    rej = np.zeros(16, dtype=np.int64)
    ad_log = np.zeros((MAXT, 3))      # (closed-trade count, new level, bar index)
    n_ad = 0

    # per-direction state (index 0 = long, 1 = short), in mirrored price space
    pool = np.zeros((2, 64, 6))
    stage = np.zeros(2, dtype=np.int64)
    sweep_bar = np.zeros(2, dtype=np.int64)
    ext = np.zeros(2); sweep_q = np.zeros(2); sweep_kind = np.zeros(2)
    mss_lvl = np.zeros(2); disp_str = np.zeros(2); mss_bar = np.zeros(2, dtype=np.int64)
    mss_margin = np.zeros(2)
    fvg_top = np.zeros(2); fvg_bot = np.zeros(2); fvg_bar = np.full(2, -1, dtype=np.int64)
    fvg_sz = np.zeros(2); touched = np.zeros(2, dtype=np.int64); fvg_org = np.zeros(2)
    ob_lo = np.full(2, np.nan); ob_hi = np.full(2, np.nan)
    last_sh = np.full(2, np.nan)                    # last confirmed structure high (mirrored)
    prev_src = np.full((2, 3), np.nan)              # last seen HTF level sources
    # previous liquidity-session range
    cur_ls = 0; ls_hi = np.nan; ls_lo = np.nan

    # position
    in_pos = False; pend = False
    p_dir = 0; p_entry = 0.0; p_sl = 0.0; p_slnext = 0.0; p_tp = 0.0; p_risk = 0.0
    p_real = 0.0; p_rem = 1.0; p_part = False; p_be = False; p_trail = False
    p_mfe = 0.0; p_mae = 0.0; p_bars = 0; p_row = 0
    pend_dir = 0; pend_sl = 0.0; pend_tp = 0.0; pend_risk = 0.0

    # day / risk state
    cur_day = -1; day_trades = 0; day_pnl = 0.0; consec = 0; last_entry_bar = -10 ** 9
    # adaptive state
    ad_level = 0; ad_last_change = 0; closed = 0; ad_idle_cnt = 0
    hist_r = np.zeros(50); hist_b = np.zeros((50, 4), dtype=np.int64); hist_n = 0
    pen = np.zeros((4, 2))

    warm = 260
    for i in range(warm, n):
        a = atr[i]
        if np.isnan(a) or a <= 0:
            continue
        if day[i] != cur_day:
            cur_day = day[i]; day_trades = 0; day_pnl = 0.0; consec = 0
            # idle decay: tightened filters cannot starve the engine of the trades it needs to relax
            ad_idle_cnt += 1
            if ad_on and ad_level > 0 and ad_idle > 0 and ad_idle_cnt >= ad_idle:
                ad_level -= 1; ad_idle_cnt = 0; ad_last_change = closed
                ad_log[n_ad, 0] = closed; ad_log[n_ad, 1] = ad_level; ad_log[n_ad, 2] = i
                n_ad += 1

        # ---------------- fills and position management on 1-minute bars -------------
        for k in range(ms[i], me[i]):
            if pend and k == ms[i]:
                pend = False
                s = pend_dir
                sprk = (m_ao[k] - m_bo[k]) * spread_mult
                if s > 0:
                    e = m_bo[k] + sprk + slip
                else:
                    e = -(m_bo[k]) + slip
                if e > pend_sl and e < pend_tp and eod[i] == 0:
                    in_pos = True; p_dir = s; p_entry = e; p_sl = pend_sl; p_slnext = pend_sl
                    p_tp = pend_tp; p_risk = pend_risk; p_real = 0.0; p_rem = 1.0
                    p_part = False; p_be = False; p_trail = False; p_mfe = 0.0; p_mae = 0.0
                    p_bars = 0
                    T[p_row, 2] = k; T[p_row, 4] = s * e; T[p_row, 25] = sprk
                    day_trades += 1; last_entry_bar = i
                else:
                    nt -= 1                       # gap through stop/target: order cancelled
            if in_pos:
                s = p_dir
                sprk = (m_ah[k] - m_bh[k]) * spread_mult
                if s > 0:
                    xo = m_bo[k]; xh = m_bh[k]; xl = m_bl[k]; xc = m_bc[k]
                else:                              # shorts exit on the ask (mirrored)
                    sp_o = (m_ao[k] - m_bo[k]) * spread_mult
                    sp_l = (m_al[k] - m_bl[k]) * spread_mult
                    sp_c = (m_ac[k] - m_bc[k]) * spread_mult
                    xo = -(m_bo[k] + sp_o); xh = -(m_bl[k] + sp_l)
                    xl = -(m_bh[k] + sprk); xc = -(m_bc[k] + sp_c)
                p_sl = p_slnext
                done = False; xp = 0.0; reason = 0
                if eod[i] == 1 or (max_hold > 0 and p_bars >= max_hold):
                    done = True; xp = xo; reason = 4
                elif xo <= p_sl:
                    done = True; xp = xo - slip; reason = 1
                elif xl <= p_sl:
                    done = True; xp = p_sl - slip; reason = 1
                elif xh >= p_tp:
                    done = True; xp = p_tp; reason = 2
                if done and reason == 1:
                    if p_trail:
                        reason = 5
                    elif p_be:
                        reason = 3
                if not done:
                    if part_on and (not p_part) and xh >= p_entry + part_r * p_risk:
                        p_part = True; p_real += part_frac * part_r * p_risk; p_rem = 1.0 - part_frac
                    if be_on and (not p_be) and xh >= p_entry + be_r * p_risk:
                        p_be = True
                        nb = p_entry + be_off * p_risk
                        if nb > p_slnext:
                            p_slnext = nb
                    if xh - p_entry > p_mfe:
                        p_mfe = xh - p_entry
                    if p_entry - xl > p_mae:
                        p_mae = p_entry - xl
                else:
                    if reason == 2 and p_tp - p_entry > p_mfe:
                        p_mfe = p_tp - p_entry
                    if reason != 2 and p_entry - xp > p_mae:
                        p_mae = p_entry - xp
                    pnl_r = (p_real + p_rem * (xp - p_entry)) / p_risk
                    T[p_row, 3] = k; T[p_row, 7] = s * xp; T[p_row, 8] = pnl_r
                    T[p_row, 20] = p_mfe / p_risk; T[p_row, 21] = p_mae / p_risk
                    T[p_row, 23] = reason
                    in_pos = False
                    day_pnl += risk_pct * pnl_r
                    if pnl_r < -0.05:
                        consec += 1
                    elif pnl_r > 0.05:
                        consec = 0
                    # ---------- adaptive engine: update on every completed trade ----------
                    closed += 1; ad_idle_cnt = 0
                    slot = (closed - 1) % 50
                    hist_r[slot] = pnl_r
                    hist_b[slot, 0] = int(T[p_row, 16]) - 1
                    hist_b[slot, 1] = int(T[p_row, 15])
                    hist_b[slot, 2] = 1 if T[p_row, 14] >= 3 else 0
                    hist_b[slot, 3] = 1 if T[p_row, 18] >= 4 else 0
                    if hist_n < 50:
                        hist_n += 1
                    if ad_on and closed >= ad_min_n:
                        m = ad_win if ad_win < hist_n else hist_n
                        sr = 0.0
                        for q in range(m):
                            sr += hist_r[(closed - 1 - q) % 50]
                        expw = sr / m
                        if closed - ad_last_change >= ad_cd:
                            newl = ad_level
                            if expw < ad_tight and ad_level < ad_max:
                                newl = ad_level + 1
                            elif expw > ad_relax and ad_level > 0:
                                newl = ad_level - 1
                            if newl != ad_level:
                                ad_level = newl; ad_last_change = closed
                                ad_log[n_ad, 0] = closed; ad_log[n_ad, 1] = newl; ad_log[n_ad, 2] = i
                                n_ad += 1
                        # condition buckets over the last (up to) 50 trades
                        for f in range(4):
                            for v in range(2):
                                cnt = 0; sm = 0.0
                                for q in range(hist_n):
                                    if hist_b[q, f] == v:
                                        cnt += 1; sm += hist_r[q]
                                pen[f, v] = ad_bpen if (cnt >= ad_bn and sm / cnt < ad_bexp) else 0.0
            if in_pos and k == me[i] - 1:
                p_bars += 1
                if trail_on and p_mfe >= trail_start * p_risk:
                    hi_m = h[i] if p_dir > 0 else -l[i]
                    ns = hi_m - trail_atr * a
                    if ns > p_slnext:
                        p_slnext = ns; p_trail = True

        # ---------------- effective (adaptive) thresholds -----------------------------
        disp_min = disp_min0 + ad_level * ad_sdisp
        fvg_min = fvg_min0 + ad_level * ad_sfvg
        min_score = min_score0 + ad_level * ad_step
        htf_req = htf_req0 + (1 if ad_level >= 2 else 0)
        if htf_req > n_htf:
            htf_req = n_htf

        # ---------------- previous liquidity-session range ---------------------------
        new_sess_hi = np.nan; new_sess_lo = np.nan
        if lsess[i] != cur_ls:
            if cur_ls != 0 and not np.isnan(ls_hi):
                new_sess_hi = ls_hi; new_sess_lo = ls_lo
            cur_ls = lsess[i]; ls_hi = h[i]; ls_lo = l[i]
        else:
            if h[i] > ls_hi:
                ls_hi = h[i]
            if l[i] < ls_lo:
                ls_lo = l[i]

        tol = eq_tol * a
        for d in range(2):
            s = 1.0 if d == 0 else -1.0
            if d == 0:
                hi = h[i]; lo = l[i]; op = o[i]; cl = c[i]
            else:
                hi = -l[i]; lo = -h[i]; op = -o[i]; cl = -c[i]
            pl = pool[d]

            # ---- structure pivot (MSS reference) ----
            new_sh = np.nan; new_sh_bar = -1
            if d == 0:
                if _pivot_high(h, i, struct_len):
                    new_sh = h[i - struct_len]; new_sh_bar = i - struct_len
            else:
                if _pivot_low(l, i, struct_len):
                    new_sh = -l[i - struct_len]; new_sh_bar = i - struct_len
            if not np.isnan(new_sh):
                last_sh[d] = new_sh

            # ---- age out / add liquidity pools ----
            for q in range(64):
                if pl[q, 5] == 1.0:
                    lim = hliq_age if pl[q, 1] >= 4 else liq_age
                    if i - pl[q, 2] > lim:
                        pl[q, 5] = 0.0
            if use_int:
                if d == 0:
                    if _pivot_low(l, i, swing_len):
                        _add_level(pl, l[i - swing_len], 1, i - swing_len, tol, KW)
                elif _pivot_high(h, i, swing_len):
                    _add_level(pl, -h[i - swing_len], 1, i - swing_len, tol, KW)
            if use_ext:
                if d == 0:
                    if _pivot_low(l, i, ext_len):
                        _add_level(pl, l[i - ext_len], 2, i - ext_len, tol, KW)
                elif _pivot_high(h, i, ext_len):
                    _add_level(pl, -h[i - ext_len], 2, i - ext_len, tol, KW)
            # HTF sources: prev 1H, prev 4H, prev day (col order: 1hH 1hL 4hH 4hL dH dL)
            for src in range(3):
                enabled = (src == 0 and use_1h) or (src == 1 and use_4h) or (src == 2 and use_day)
                v = lv[i, src * 2 + 1] if d == 0 else -lv[i, src * 2]
                if enabled and not np.isnan(v) and v != prev_src[d, src]:
                    if v < lo:
                        _add_level(pl, v, 4 if src == 0 else (5 if src == 1 else 7), i, tol, KW)
                prev_src[d, src] = v
            if use_sess and not np.isnan(new_sess_hi):
                v = new_sess_lo if d == 0 else -new_sess_hi
                if v < lo:
                    _add_level(pl, v, 6, i, tol, KW)

            # ---- sweeps ----
            best_w = 0.0; best_kind = 0.0; cnt = 0; sw_ext = lo
            for q in range(64):
                if pl[q, 5] == 0.0 or pl[q, 2] >= i:
                    continue
                price = pl[q, 0]
                swept = False
                if pl[q, 3] < 0:
                    if lo < price:
                        if cl > price:
                            swept = True; pl[q, 4] = lo
                        else:
                            pl[q, 3] = i; pl[q, 4] = lo
                else:
                    if lo < pl[q, 4]:
                        pl[q, 4] = lo
                    if cl > price and i - pl[q, 3] <= reclaim:
                        swept = True
                    elif i - pl[q, 3] >= reclaim:
                        pl[q, 5] = 0.0                  # accepted below: broken, not swept
                if swept:
                    pl[q, 5] = 0.0
                    kq = int(pl[q, 1]); wq = KW[kq]
                    cnt += 1
                    if wq > best_w:
                        best_w = wq; best_kind = kq
                    if pl[q, 4] < sw_ext:
                        sw_ext = pl[q, 4]
            if cnt > 0 and best_w >= min_liq_w and stage[d] <= 1:
                lvl = last_sh[d]
                if not np.isnan(lvl) and lvl > cl:
                    gw = best_w + 0.1 * (cnt - 1)
                    if gw > 1.0:
                        gw = 1.0
                    rejn = (cl - sw_ext) / a
                    if rejn > 1.0:
                        rejn = 1.0
                    if rejn < 0.0:
                        rejn = 0.0
                    qv = 0.6 * gw + 0.4 * rejn
                    if stage[d] == 1 and ext[d] < sw_ext:
                        sw_ext = ext[d]
                    stage[d] = 1; sweep_bar[d] = i; ext[d] = sw_ext; sweep_q[d] = qv
                    sweep_kind[d] = best_kind; mss_lvl[d] = lvl; disp_str[d] = 0.0
                    fvg_bar[d] = -1; touched[d] = 0; ob_lo[d] = np.nan; ob_hi[d] = np.nan

            # ---- setup state machine ----
            signal = False
            if stage[d] == 1:
                if lo < ext[d]:
                    ext[d] = lo
                if new_sh_bar >= 0 and new_sh_bar < sweep_bar[d] and new_sh < mss_lvl[d] and new_sh > cl:
                    mss_lvl[d] = new_sh
                body = cl - op; rng = hi - lo
                if body > 0 and rng > 0 and not np.isnan(avgr[i]):
                    if body >= disp_min * a and body / rng >= disp_body and rng >= disp_exp * avgr[i] \
                            and (hi - cl) / rng <= disp_cp:
                        st = body / a
                        if st > disp_str[d]:
                            if disp_str[d] == 0.0:
                                for kk in range(1, ob_look + 1):
                                    if s * c[i - kk] < s * o[i - kk]:
                                        if d == 0:
                                            ob_lo[d] = l[i - kk]; ob_hi[d] = h[i - kk]
                                        else:
                                            ob_lo[d] = -h[i - kk]; ob_hi[d] = -l[i - kk]
                                        break
                            disp_str[d] = st
                if i - 1 >= sweep_bar[d]:
                    h2 = h[i - 2] if d == 0 else -l[i - 2]
                    if lo > h2 and lo - h2 >= fvg_min * a:
                        fvg_top[d] = lo; fvg_bot[d] = h2; fvg_bar[d] = i; fvg_sz[d] = (lo - h2) / a
                        l1 = l[i - 1] if d == 0 else -h[i - 1]
                        l2 = l[i - 2] if d == 0 else -h[i - 2]
                        fvg_org[d] = l1 if l1 < l2 else l2
                if cl > mss_lvl[d] and disp_str[d] > 0.0:
                    stage[d] = 2; mss_bar[d] = i; mss_margin[d] = (cl - mss_lvl[d]) / a
                elif i - sweep_bar[d] > setup_max:
                    stage[d] = 0
            elif stage[d] == 2:
                if touched[d] == 0 and i <= mss_bar[d] + fvg_wait:
                    h2 = h[i - 2] if d == 0 else -l[i - 2]
                    if lo > h2 and lo - h2 >= fvg_min * a:
                        fvg_top[d] = lo; fvg_bot[d] = h2; fvg_bar[d] = i; fvg_sz[d] = (lo - h2) / a
                        l1 = l[i - 1] if d == 0 else -h[i - 1]
                        l2 = l[i - 2] if d == 0 else -h[i - 2]
                        fvg_org[d] = l1 if l1 < l2 else l2
                if fvg_bar[d] < 0:
                    if i >= mss_bar[d] + fvg_wait:
                        stage[d] = 0
                elif i > fvg_bar[d]:
                    dead = False
                    if lo < ext[d]:
                        dead = True
                    elif mitig_mode == 0 and cl < fvg_bot[d]:
                        dead = True
                    elif mitig_mode == 1 and lo < fvg_bot[d]:
                        dead = True
                    elif i - fvg_bar[d] > fvg_age:
                        dead = True
                    if dead:
                        stage[d] = 0
                    else:
                        if lo <= fvg_top[d] - fvg_depth * (fvg_top[d] - fvg_bot[d]):
                            touched[d] = 1
                        mid = 0.5 * (fvg_top[d] + fvg_bot[d])
                        if touched[d] == 1 and cl > op and ((not confirm_mid) or cl > mid):
                            signal = True

            if not signal:
                continue
            stage[d] = 0                                   # one signal per setup, always

            # ---------------- signal evaluation ----------------
            anchor = ext[d] if sl_mode == 0 else fvg_org[d]
            sl = anchor - sl_buf * a
            risk = cl - sl
            stop_atr = risk / a
            has_ob = 0
            if not np.isnan(ob_hi[d]):
                if ob_hi[d] >= fvg_bot[d] - 0.25 * a and ob_lo[d] <= fvg_top[d]:
                    has_ob = 1
            sd = 1 if d == 0 else -1
            hc = 0; opp1 = False; opp4 = False
            if htf_mask & 1 and b5[i] == sd:
                hc += 1
            if htf_mask & 2 and b15[i] == sd:
                hc += 1
            if htf_mask & 4:
                if b60[i] == sd:
                    hc += 1
                elif b60[i] == -sd:
                    opp1 = True
            if htf_mask & 8:
                if b240[i] == sd:
                    hc += 1
                elif b240[i] == -sd:
                    opp4 = True
            x = (disp_str[d] - disp_min0)
            if x < 0:
                x = 0.0
            if x > 1:
                x = 1.0
            sc_disp = 0.5 + 0.5 * x
            x = mss_margin[d] / 0.5
            if x > 1:
                x = 1.0
            sc_mss = 0.6 + 0.4 * x
            x = (fvg_sz[d] - fvg_min0) / 0.5
            if x < 0:
                x = 0.0
            if x > 1:
                x = 1.0
            sc_fvg = 0.5 + 0.5 * x
            sc_htf = hc / n_htf if n_htf > 0 else 0.0
            sc_sess = 1.0 if (sess[i] > 0 and kz[i] == 1) else (0.6 if sess[i] > 0 else 0.0)
            score = w_sweep * sweep_q[d] + w_disp * sc_disp + w_mss * sc_mss + w_fvg * sc_fvg \
                + w_htf * sc_htf + w_ob * has_ob + w_sess * sc_sess

            # target
            tp = cl + rr * risk
            # nearest opposing liquidity (pools of the other direction, mirrored)
            opp = pool[1 - d]
            near = np.nan
            for q in range(64):
                if opp[q, 5] == 1.0 and KW[int(opp[q, 1])] >= 0.5:
                    lvl_m = -opp[q, 0]
                    if lvl_m > cl and (np.isnan(near) or lvl_m < near):
                        near = lvl_m
            if tp_mode == 1 and not np.isnan(near):
                tr_ = (near - cl) / risk
                if tr_ >= min_tgt:
                    if tr_ > max_tgt:
                        tr_ = max_tgt
                    tp = cl + tr_ * risk

            # bucket penalties (adaptive)
            need = min_score
            if ad_on and sess[i] > 0:
                need += pen[0, sess[i] - 1] + pen[1, has_ob] + pen[2, 1 if hc >= 3 else 0] \
                    + pen[3, 1 if sweep_kind[d] >= 4 else 0]

            r = -1
            ok_sess = sess[i] > 0 and (sess_mode == 0 or sess_mode == sess[i])
            if not ok_sess:
                r = 0
            elif eod[i] == 1:
                r = 14
            elif np.isnan(atrr[i]) or atrr[i] < vol_min or atrr[i] > vol_max:
                r = 11
            elif max_spread > 0 and spr[i] * spread_mult > max_spread:
                r = 12
            elif stop_atr < min_stop or (min_stop_usd > 0 and risk < min_stop_usd):
                r = 3
            elif stop_atr > max_stop or (max_stop_usd > 0 and risk > max_stop_usd):
                r = 4
            elif hc < htf_req or (htf_veto >= 1 and opp1) or (htf_veto >= 2 and opp4):
                r = 1
            elif ob_req and has_ob == 0:
                r = 13
            elif min_room > 0 and not np.isnan(near) and (near - cl) < min_room * risk:
                r = 5
            elif score < need:
                r = 2
            elif day_trades >= max_tr_day:
                r = 6
            elif day_pnl <= -max_dloss:
                r = 7
            elif profit_lock > 0 and day_pnl >= profit_lock:
                r = 15
            elif max_consec > 0 and consec >= max_consec:
                r = 8
            elif i - last_entry_bar < cooldown:
                r = 9
            elif (in_pos and one_pos) or pend or in_pos:
                r = 10
            if r >= 0:
                rej[r] += 1
                continue
            if nt >= MAXT - 1 or i + 1 >= n:
                continue
            pend = True; pend_dir = sd; pend_sl = sl; pend_tp = tp; pend_risk = risk
            p_row = nt
            T[nt, 0] = i; T[nt, 1] = sd; T[nt, 5] = s * sl; T[nt, 6] = s * tp
            T[nt, 9] = score; T[nt, 10] = sweep_q[d]; T[nt, 11] = disp_str[d]
            T[nt, 12] = mss_margin[d]; T[nt, 13] = fvg_sz[d]; T[nt, 14] = hc; T[nt, 15] = has_ob
            T[nt, 16] = sess[i]; T[nt, 17] = kz[i]; T[nt, 18] = sweep_kind[d]; T[nt, 19] = stop_atr
            T[nt, 22] = ad_level; T[nt, 24] = risk; T[nt, 26] = need
            nt += 1

    if in_pos or pend:
        nt -= 1                                           # drop the unfinished trade
    return T[:nt], rej, ad_log[:n_ad]


# --------------------------------------------------------------------------
# Python wrapper + statistics
# --------------------------------------------------------------------------
def run(D, **over):
    P = make_params(**over)
    PIDX = np.arange(len(PKEYS), dtype=np.int64)
    T, rej, ad = run_core(D["o"], D["h"], D["l"], D["c"], D["atr"], D["atrr"], D["avgr"],
                          D["ms"], D["me"], D["sess"], D["kz"], D["lsess"], D["eod"], D["day"],
                          D["b5"], D["b15"], D["b60"], D["b240"], D["lv"], D["spr"],
                          D["m_bo"], D["m_bh"], D["m_bl"], D["m_bc"], D["m_ao"], D["m_ah"],
                          D["m_al"], D["m_ac"], P, PIDX)
    t = pd.DataFrame(T, columns=TCOLS)
    t["sig_time"] = D["idx"][t["sig_bar"].astype(int)] + pd.Timedelta(minutes=D["tf"])
    t["entry_time"] = D["m_idx"][t["entry_m1"].astype(int)]
    t["exit_time"] = D["m_idx"][t["exit_m1"].astype(int)] + pd.Timedelta(minutes=1)
    t["tf"] = D["tf"]
    t.attrs["rej"] = dict(zip(REJ_NAMES, rej.tolist()))
    t.attrs["ad_log"] = ad
    t.attrs["risk_pct"] = dict(DEFAULTS, **over)["risk_pct"]
    return t


def stats(t, risk_pct=0.5):
    """Summary statistics in R and in account % (compounded at risk_pct per trade)."""
    n = len(t)
    if n == 0:
        return dict(trades=0)
    r = t["R"].to_numpy()
    wins = r[r > 0]; losses = r[r <= 0]
    gp = wins.sum(); gl = -losses.sum()
    eq = np.cumprod(1 + risk_pct / 100 * r)
    peak = np.maximum.accumulate(np.concatenate([[1.0], eq]))[1:]
    dd = (eq / peak - 1).min() * 100
    cr = np.cumsum(r); ddr = (cr - np.maximum.accumulate(np.concatenate([[0.0], cr]))[1:]).min()
    streak = 0; mx = 0
    for x in r:
        streak = streak + 1 if x <= 0 else 0
        mx = max(mx, streak)
    se = r.std(ddof=1) / np.sqrt(n) if n > 1 else np.nan
    return dict(trades=n, win_rate=round(100 * len(wins) / n, 1),
                pf=round(gp / gl, 2) if gl > 0 else np.inf,
                exp_r=round(r.mean(), 3), t_stat=round(r.mean() / se, 2) if se and se > 0 else np.nan,
                net_r=round(r.sum(), 1), net_pct=round((eq[-1] - 1) * 100, 1),
                max_dd_pct=round(dd, 1), max_dd_r=round(ddr, 1),
                avg_win_r=round(wins.mean(), 2) if len(wins) else 0.0,
                avg_loss_r=round(losses.mean(), 2) if len(losses) else 0.0,
                max_consec_loss=mx,
                avg_mfe_r=round(t["mfe_r"].mean(), 2), avg_mae_r=round(t["mae_r"].mean(), 2))


def split(t, start, end):
    s = pd.Timestamp(start, tz="UTC"); e = pd.Timestamp(end, tz="UTC")
    return t[(t["entry_time"] >= s) & (t["entry_time"] < e)]
