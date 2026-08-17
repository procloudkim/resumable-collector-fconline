from __future__ import annotations

from pathlib import Path
from typing import Optional

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs" / "dfinfo"


def ensure_dirs() -> None:
    DOCS.mkdir(parents=True, exist_ok=True)


def find_file(*cands: str) -> Optional[Path]:
    for c in cands:
        p = ROOT / c
        if p.exists():
            return p
    return None


def detect_date_col(df: pd.DataFrame) -> Optional[str]:
    for c in ["날짜", "date", "DATE", "published_at", "updated_at"]:
        if c in df.columns:
            return c
    # heuristic: max parsable
    best, cnt = None, -1
    for c in df.columns:
        try:
            n = int(pd.to_datetime(df[c], errors="coerce").notna().sum())
        except Exception:
            n = -1
        if n > cnt:
            best, cnt = c, n
    return best


def df_info_md(title: str, path: Path, df: pd.DataFrame) -> str:
    lines: list[str] = []
    lines.append(f"# {title}")
    lines.append("")
    lines.append(f"- 경로: `{path.as_posix()}`")
    lines.append(f"- shape: {df.shape[0]:,} × {df.shape[1]:,}")
    # date range
    dcol = detect_date_col(df)
    if dcol and dcol in df.columns:
        try:
            dt = pd.to_datetime(df[dcol], errors="coerce")
            if dt.notna().any():
                lines.append(f"- 기간: {dt.min().date()} ~ {dt.max().date()}")
        except Exception:
            pass
    # dtypes summary (first 20 columns)
    lines.append("- 컬럼(dtypes) 예시:")
    for c, t in df.dtypes.astype(str).items():
        lines.append(f"  - {c}: {t}")
        if len(lines) > 30:  # cap lines
            lines.append("  - ...")
            break
    # null counts (head 20 columns)
    lines.append("- 결측치 개수(상위 20개 컬럼):")
    na = df.isna().sum().sort_values(ascending=False)
    for c, n in na.iloc[:20].items():
        if n > 0:
            lines.append(f"  - {c}: {int(n):,}")
    # head sample
    lines.append("\n- 샘플 3행:")
    try:
        sample = df.head(3).to_markdown(index=False)
        lines.append(sample)
    except Exception:
        # fallback simple csv-like
        lines.append(df.head(3).to_csv(index=False))
    return "\n".join(lines) + "\n"


def write_md(name: str, content: str) -> Path:
    out = DOCS / name
    out.write_text(content, encoding="utf-8")
    return out


def main() -> int:
    ensure_dirs()

    # TopDaily
    p_top = find_file(
        "analytics/clean/top_daily_record.clean.ko.strip.csv",
        "analytics/clean/top_daily_record.clean.ko.csv",
        "analytics/clean/top_daily_record.clean.csv",
        "analytics/game/top_daily_record.csv",
    )
    if p_top:
        df_top = pd.read_csv(p_top)
        write_md("DFINFO_top_daily_record.md", df_info_md("TopDailyRecord", p_top, df_top))

    # BestPrice
    p_best = find_file(
        "analytics/clean/best_price_daily.clean.names.strip.csv",
        "analytics/clean/best_price_daily.clean.names.csv",
        "analytics/clean/best_price_daily.clean.ko.csv",
        "analytics/clean/best_price_daily.clean.csv",
        "analytics/game/best_price_daily.csv",
    )
    if p_best:
        df_best = pd.read_csv(p_best)
        write_md("DFINFO_best_price_daily.md", df_info_md("BestPriceDaily", p_best, df_best))

    # YouTube comments
    p_comm = find_file(
        "analytics/clean/comments.clean.csv",
        "analytics/youtube/comments.csv",
    )
    if p_comm:
        df_com = pd.read_csv(p_comm)
        write_md("DFINFO_comments.md", df_info_md("YouTube Comments", p_comm, df_com))

    # Events
    p_evt = find_file("config/events.csv")
    if p_evt:
        df_evt = pd.read_csv(p_evt)
        write_md("DFINFO_events.md", df_info_md("Events", p_evt, df_evt))

    print(f"[OK] wrote md files to {DOCS}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
