from __future__ import annotations

"""
EDA for data/processed/daily_trade.csv

Outputs a concise summary to stdout and saves a markdown report to
data/reports/daily_trade_eda.md
"""

import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    csv_path = Path("data/processed/daily_trade.csv")
    if not csv_path.exists():
        print(f"[ERR] CSV not found: {csv_path}")
        return 1
    try:
        import pandas as pd
    except Exception as e:
        print(f"[ERR] pandas not available: {e}")
        return 2

    pd.options.display.float_format = "{:,.2f}".format
    df = pd.read_csv(csv_path)
    rows = len(df)
    cols = list(df.columns)

    # Ensure expected columns exist
    for c in [
        "date",
        "spid",
        "player_name",
        "avg_price",
        "max_price",
        "min_price",
        "trade_count",
        "max_enhance_level",
        "source",
    ]:
        if c not in df.columns:
            df[c] = None

    # Coerce numeric
    for c in ["avg_price", "max_price", "min_price", "trade_count", "max_enhance_level"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")

    date_min = df["date"].min() if "date" in df.columns else None
    date_max = df["date"].max() if "date" in df.columns else None
    n_dates = df["date"].nunique(dropna=True) if "date" in df.columns else None
    n_spids = df["spid"].nunique(dropna=True) if "spid" in df.columns else None

    nulls = df.isna().sum().sort_values(ascending=False)
    dup_key_cnt = int(df.duplicated(subset=["date", "spid"]).sum()) if set(["date","spid"]).issubset(df.columns) else None

    num_cols = ["avg_price", "max_price", "min_price", "trade_count", "max_enhance_level"]
    desc = df[num_cols].describe(percentiles=[0.25, 0.5, 0.75])

    consistency = {}
    if set(["avg_price", "max_price"]).issubset(df.columns):
        m = df[["avg_price", "max_price"]].dropna()
        consistency["max_lt_avg"] = int((m["max_price"] < m["avg_price"]).sum())
    if set(["min_price", "max_price"]).issubset(df.columns):
        m2 = df[["min_price", "max_price"]].dropna()
        consistency["max_lt_min"] = int((m2["max_price"] < m2["min_price"]).sum())

    coverage = {}
    for c in num_cols:
        nonnull = int(df[c].notna().sum())
        coverage[c] = {
            "nonnull": nonnull,
            "rate": round(100.0 * nonnull / rows, 2) if rows else 0.0,
        }

    top_spids = []
    if "spid" in df.columns:
        vc = df["spid"].value_counts().head(10)
        for spid, cnt in vc.items():
            top_spids.append({"spid": int(spid) if pd.notna(spid) else None, "rows": int(cnt)})

    per_date = []
    if "date" in df.columns:
        vc2 = df["date"].value_counts().sort_index()
        for d, cnt in list(vc2.items())[:10]:
            per_date.append({"date": d, "rows": int(cnt)})

    # Build markdown
    lines: list[str] = []
    lines.append(f"File: `{csv_path}`")
    lines.append(f"Rows: {rows}")
    lines.append(f"Columns: {cols}")
    lines.append(f"Dates: {n_dates} (min={date_min}, max={date_max})")
    lines.append(f"Unique SPIDs: {n_spids}")
    lines.append("")
    lines.append("Null counts (top):")
    for k, v in nulls.head(8).items():
        lines.append(f"- {k}: {int(v)}")
    if dup_key_cnt is not None:
        lines.append(f"- Duplicates (date,spid): {dup_key_cnt}")
    lines.append("")
    lines.append("Coverage:")
    for k, info in coverage.items():
        lines.append(f"- {k}: {info['nonnull']} ({info['rate']}%)")
    lines.append("")
    lines.append("Consistency checks:")
    for k, v in consistency.items():
        lines.append(f"- {k}: {v}")
    lines.append("")
    lines.append("Numeric describe:")
    for c in num_cols:
        s = desc[c]
        lines.append(
            f"- {c}: count={int(s.get('count',0))}, mean={s.get('mean')}, min={s.get('min')}, p50={s.get('50%')}, max={s.get('max')}"
        )
    lines.append("")
    lines.append("Top SPIDs by rows:")
    for it in top_spids:
        lines.append(f"- spid={it['spid']}: rows={it['rows']}")
    lines.append("")
    lines.append("Rows per date (head):")
    for it in per_date:
        lines.append(f"- {it['date']}: {it['rows']}")

    out_dir = Path("data/reports")
    out_dir.mkdir(parents=True, exist_ok=True)
    report_path = out_dir / "daily_trade_eda.md"
    report = "\n".join(lines)
    report_path.write_text(report, encoding="utf-8")

    # Print concise stdout summary
    print(report)
    print(f"\n[SAVED] {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

