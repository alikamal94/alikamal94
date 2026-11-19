"""Offline SYNTAX check of the generated Pine scripts with the open-source `pynescript` parser.

This is NOT TradingView's compiler: it validates grammar only (no types, no built-in signatures).
Each top-level statement is parsed on its own so one slow or failing block is reported precisely.

    pip install pynescript && python tools/syntax_check.py
"""
import os, sys, multiprocessing as mp

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def chunks(text):
    out, cur, start = [], [], 1
    for no, ln in enumerate(text.split("\n"), 1):
        top = ln[:1] not in (" ", "\t", "") and not ln.startswith("//")
        if top and cur:
            out.append((start, "\n".join(cur) + "\n")); cur = []
        if not cur:
            start = no
        if ln.strip() and not (ln.startswith("//") and not cur):
            cur.append(ln)
    if cur:
        out.append((start, "\n".join(cur) + "\n"))
    return out


def work(item):
    line, src = item
    from pynescript.ast import parse
    try:
        parse(src)
        return line, None
    except Exception as ex:                      # noqa: BLE001
        return line, str(ex).replace("\n", " ")[:300]


if __name__ == "__main__":
    bad = 0
    for f in sys.argv[1:] or ["XAUUSD_ICT_Adaptive_Strategy.pine", "XAUUSD_ICT_Adaptive_Indicator.pine"]:
        items = chunks(open(os.path.join(HERE, f)).read())
        with mp.Pool(4) as pool:
            res = [pool.apply_async(work, (it,)) for it in items]
            fails, slow = [], []
            for it, r in zip(items, res):
                try:
                    line, err = r.get(timeout=240)
                    if err:
                        fails.append((line, err))
                except mp.TimeoutError:
                    slow.append(it[0])
            pool.terminate()
        print(f"{f}: {len(items)} top-level statements, {len(fails)} syntax errors, {len(slow)} timed out")
        for line, err in fails:
            print(f"  line {line}: {err}")
        for line in slow:
            print(f"  line {line}: parser timeout (not checked)")
        bad += len(fails)
    sys.exit(1 if bad else 0)
