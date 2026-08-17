from __future__ import annotations

import importlib
from pathlib import Path
import pandas as pd

def ver(pkg: str) -> str:
    try:
        m = importlib.import_module(pkg)
        return getattr(m, "__version__", "?")
    except Exception as e:
        return f"ERR:{type(e).__name__}"


def safe_shape_csv(p: Path) -> str:
    try:
        df = pd.read_csv(p, nrows=5, encoding="utf-8-sig")
        # try whole shape cheaply
        df2 = pd.read_csv(p, encoding="utf-8-sig", low_memory=False)
        return f"{p} -> {df2.shape} cols_head={list(df2.columns)[:6]}"
    except Exception as e:
        return f"{p} -> ERR:{e}"


def main():
    print("versions:", {
        "python": importlib.import_module('sys').version.split()[0],
        "streamlit": ver("streamlit"),
        "pandas": ver("pandas"),
        "plotly": ver("plotly"),
    })

    # Where will loader read from?
    from app.dashboard_loader import load_bestprice, load_topdaily, load_events

    tb, pb = load_bestprice()
    tt, pt = load_topdaily()
    te, pe = load_events()

    print("loader_paths:", {"bestprice": str(pb), "topdaily": str(pt), "events": str(pe)})
    print("shapes:", {"bestprice": getattr(tb, 'shape', None), "topdaily": getattr(tt, 'shape', None), "events": getattr(te, 'shape', None)})

    # Quick file presence check
    cand = [
        Path("analytics/new_analytics/best_price_daily.clean.names.strip.fixed.csv"),
        Path("analytics/new_analytics/top_daily_record.clean.ko.strip.fixed.csv"),
        Path("analytics/clean/best_price_daily.clean.names.strip.csv"),
        Path("analytics/clean/top_daily_record.clean.ko.strip.csv"),
        Path("config/event_presets_ko.json"),
        Path("config/events.csv"),
    ]
    for p in cand:
        print("exists:", p, p.exists())

    # Validate a couple CSVs if present
    for p in cand:
        if p.exists() and p.suffix == ".csv":
            print(safe_shape_csv(p))


if __name__ == "__main__":
    main()

