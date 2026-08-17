from __future__ import annotations

"""
Robust summary export for BestPrice/TopDaily/YouTube.

Writes analytics/exports/summary_stats.txt with robust metrics
(median, trimmed mean), avoiding mean-only skew by extreme outliers.
"""

from pathlib import Path
from typing import Optional

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
ANALYTICS = ROOT / "analytics"
CLEAN = ANALYTICS / "clean"
GAME = ANALYTICS / "game"
EXPORTS = ANALYTICS / "exports"


def _ensure_dirs() -> None:
    EXPORTS.mkdir(parents=True, exist_ok=True)


def _find_file(*candidates: str) -> Optional[Path]:
    for n in candidates:
        p = ROOT / n
        if p.exists():
            return p
    return None


def _load_df(path_candidates: list[str]) -> Optional[pd.DataFrame]:
    p = _find_file(*path_candidates)
    if not p:
        return None
    try:
        return pd.read_csv(p)
    except Exception:
        return None


def _detect_date_col(df: pd.DataFrame) -> Optional[str]:
    for c in ["날짜", "date", "DATE"]:
        if c in df.columns:
            return c
    for c in df.columns:
        try:
            if pd.to_datetime(df[c], errors="coerce").notna().sum() > len(df) // 2:
                return c
        except Exception:
            pass
    return None


def main() -> int:
    _ensure_dirs()

    df_t = _load_df([
        "analytics/clean/top_daily_record.clean.ko.strip.csv",
        "analytics/clean/top_daily_record.clean.ko.csv",
        "analytics/clean/top_daily_record.clean.csv",
        "analytics/game/top_daily_record.csv",
    ])
    df_b = _load_df([
        "analytics/clean/best_price_daily.clean.names.strip.csv",
        "analytics/clean/best_price_daily.clean.names.csv",
        "analytics/clean/best_price_daily.clean.ko.csv",
        "analytics/clean/best_price_daily.clean.csv",
        "analytics/game/best_price_daily.csv",
    ])
    df_c = _load_df([
        "analytics/clean/comments.clean.csv",
        "analytics/youtube/comments.csv",
    ])

    lines: list[str] = []

    # TopDaily
    if df_t is not None:
        lines.append("[TopDaily]")
        lines.append(f"rows={len(df_t)}")
        val_col = "출전_기록" if "출전_기록" in df_t.columns else ("출전" if "출전" in df_t.columns else None)
        if val_col:
            v = pd.to_numeric(df_t[val_col], errors="coerce").dropna()
            if not v.empty:
                lines.append(f"출전_기록 평균={v.mean():.2f}")
                lines.append(f"출전_기록 중앙값={v.median():.2f}")

    # BestPrice (robust)
    if df_b is not None:
        lines.append("\n[BestPrice]")
        lines.append(f"rows={len(df_b)}")
        price_col = "거래 가격" if "거래 가격" in df_b.columns else ("price_value" if "price_value" in df_b.columns else None)
        if price_col:
            s = pd.to_numeric(df_b[price_col], errors="coerce").dropna()
            if not s.empty:
                mean_all = float(s.mean())
                median = float(s.median())
                p90 = float(s.quantile(0.90))
                p99 = float(s.quantile(0.99))
                q01 = float(s.quantile(0.01))
                q99 = float(s.quantile(0.99))
                trimmed = s[(s >= q01) & (s <= q99)]
                mean_trim = float(trimmed.mean()) if not trimmed.empty else mean_all

                latest_year_mean = None
                dt_col = _detect_date_col(df_b) or "date"
                try:
                    dt = pd.to_datetime(df_b[dt_col], errors="coerce")
                    if dt.notna().any():
                        ly = int(dt.dt.year.max())
                        s_yr = pd.to_numeric(df_b.loc[dt.dt.year == ly, price_col], errors="coerce").dropna()
                        if not s_yr.empty:
                            latest_year_mean = float(s_yr.mean())
                except Exception:
                    pass

                lines.append(f"거래 가격 평균={mean_all:,.2f}")
                lines.append(f"거래 가격 중앙값={median:,.2f}")
                lines.append(f"거래 가격 p90={p90:,.2f}")
                lines.append(f"거래 가격 p99={p99:,.2f}")
                lines.append(f"거래 가격 절사평균(p1-p99)={mean_trim:,.2f}")
                if latest_year_mean is not None:
                    lines.append(f"거래 가격 최근연도 평균={latest_year_mean:,.2f}")

    # YouTube
    if df_c is not None and len(df_c) > 0:
        lines.append("\n[YouTube]")
        lines.append(f"rows={len(df_c)}")
        sent_col = "sentiment_label" if "sentiment_label" in df_c.columns else ("sentiment" if "sentiment" in df_c.columns else None)
        if sent_col:
            vc = df_c[sent_col].value_counts(normalize=True)
            for k, v in vc.items():
                lines.append(f"{k}: {v*100:.1f}%")

    out = EXPORTS / "summary_stats.txt"
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"[OK] wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

