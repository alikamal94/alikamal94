"""Generates the two deliverable scripts from the shared template so their logic cannot diverge.

    python build.py   ->  XAUUSD_ICT_Adaptive_Strategy.pine, XAUUSD_ICT_Adaptive_Indicator.pine
"""
import os
here = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(here, "src", "ict_adaptive.template.pine")).read().split("\n")
for kind, name in (("STRATEGY", "XAUUSD_ICT_Adaptive_Strategy.pine"), ("INDICATOR", "XAUUSD_ICT_Adaptive_Indicator.pine")):
    out, keep = [], True
    for ln in src:
        t = ln.strip()
        if t.startswith("//#IF_"):
            keep = t == "//#IF_" + kind
        elif t == "//#ENDIF":
            keep = True
        elif keep:
            out.append(ln)
    open(os.path.join(here, name), "w").write("\n".join(out))
    print(name, len(out), "lines")
