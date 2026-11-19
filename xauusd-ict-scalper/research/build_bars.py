"""Build 1-minute bid/ask OHLC bars from Dukascopy weekly tick CSVs.

Input : <data_dir>/xauusd-tick-data-YYYY/data/tick/XAUUSD_YYYY_wNN.csv.gz
        (columns: timestamp[UTC], ask, bid, ask_volume, bid_volume)
Output: <out>/xauusd_m1.parquet with columns
        ts (UTC, bar open), bo/bh/bl/bc (bid OHLC), ao/ah/al/ac (ask OHLC),
        spr (mean spread in USD), n (tick count)

Usage: python build_bars.py <data_dir> <out_dir>
"""
import glob, os, sys
from concurrent.futures import ProcessPoolExecutor
import pandas as pd


def one(path):
    df = pd.read_csv(path, usecols=["timestamp", "ask", "bid"], engine="pyarrow")
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df["spr"] = df["ask"] - df["bid"]
    g = df.groupby(df["timestamp"].dt.floor("1min"))
    out = pd.DataFrame({
        "bo": g["bid"].first(), "bh": g["bid"].max(), "bl": g["bid"].min(), "bc": g["bid"].last(),
        "ao": g["ask"].first(), "ah": g["ask"].max(), "al": g["ask"].min(), "ac": g["ask"].last(),
        "spr": g["spr"].mean(), "n": g["bid"].size(),
    })
    out.index.name = "ts"
    return out


if __name__ == "__main__":
    data_dir, out_dir = sys.argv[1], sys.argv[2]
    files = sorted(glob.glob(os.path.join(data_dir, "xauusd-tick-data-*/data/tick/*.csv.gz")))
    print(len(files), "weekly files")
    with ProcessPoolExecutor(4) as ex:
        parts = list(ex.map(one, files))
    m1 = pd.concat(parts).sort_index()
    m1 = m1[~m1.index.duplicated(keep="first")]
    os.makedirs(out_dir, exist_ok=True)
    m1.to_parquet(os.path.join(out_dir, "xauusd_m1.parquet"))
    print(m1.index[0], m1.index[-1], len(m1), "bars; mean spread", round(m1.spr.mean(), 3))
