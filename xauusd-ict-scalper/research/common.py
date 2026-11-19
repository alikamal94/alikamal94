"""Shared helpers for the research scripts."""
import os, pickle, sys
import pandas as pd
import ict_engine as E

BARS = os.environ.get("XAU_BARS", "bars/xauusd_m1.parquet")
DEV = ("2024-01-01", "2026-01-01")     # development (in-sample)
OOS = ("2026-01-01", "2027-01-01")     # out-of-sample, never used for tuning


def load(tf, cache_dir=None):
    cache_dir = cache_dir or os.path.dirname(BARS)
    pk = os.path.join(cache_dir, f"prep_{tf}.pkl")
    if os.path.exists(pk):
        return pickle.load(open(pk, "rb"))
    m1 = pd.read_parquet(BARS)
    D = E.prepare(m1, tf)
    pickle.dump(D, open(pk, "wb"))
    return D
