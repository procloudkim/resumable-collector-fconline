from __future__ import annotations

import os
from typing import Iterable, Tuple

import pandas as pd


def ensure_korean_font():
    try:
        import matplotlib
        from glob import glob
        # Try bundled font if exists
        repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
        font_dir = os.path.join(repo_root, "assets", "fonts")
        cands = glob(os.path.join(font_dir, "*.ttf")) + glob(os.path.join(font_dir, "*.otf"))
        if cands:
            from matplotlib import font_manager
            fp = font_manager.FontProperties(fname=cands[0])
            name = fp.get_name()
            font_manager.fontManager.addfont(cands[0])
            matplotlib.rcParams["font.family"] = [name]
        else:
            matplotlib.rcParams["font.family"] = [
                "Malgun Gothic",
                "AppleGothic",
                "NanumGothic",
                "DejaVu Sans",
            ]
        matplotlib.rcParams["axes.unicode_minus"] = False
    except Exception:
        pass


def overlay_events(ax, events: Iterable[Tuple[str, str, str]]):
    for ds, label, color in events:
        x = pd.to_datetime(ds, utc=True)
        ax.axvline(x=x, color=color, linestyle="--", alpha=0.6, linewidth=1)
        ymin, ymax = ax.get_ylim()
        ax.annotate(label, xy=(x, ymax), xytext=(0, 5), textcoords="offset points", ha="center", va="bottom", fontsize=9, color=color)


def plot_focus_range(in_csv: str = "data/processed/analysis_timeseries_range.csv", out_dir: str = "data/processed"):
    import matplotlib.pyplot as plt

    os.makedirs(out_dir, exist_ok=True)
    df = pd.read_csv(in_csv, parse_dates=["time_bin"])
    ensure_korean_font()

    # 긍정 비율
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(df["time_bin"], df["pos_ratio_smooth"], color="#2ca02c", label="긍정 비율")
    ax.set_title("시간대별 긍정 비율 (월드컵 집중 기간)")
    ax.set_xlabel("시간")
    ax.set_ylabel("긍정 비율")
    ax.set_ylim(0, 1)
    overlay_events(
        ax,
        [
            ("2022-11-28", "가나전 패배 ⚠️", "#d62728"),
            ("2022-12-02", "포르투갈전 승리 🏆", "#2ca02c"),
            ("2022-12-05", "브라질전 패배 ⚠️", "#d62728"),
        ],
    )
    fig.autofmt_xdate()
    fig.savefig(os.path.join(out_dir, "analysis_posratio_range_kr.png"), bbox_inches="tight", dpi=220)
    plt.close(fig)

    # 긍정/부정 수
    fig2, ax2 = plt.subplots(figsize=(10, 4))
    ax2.plot(df["time_bin"], df["pos_smooth"], label="긍정", color="#2ca02c")
    ax2.plot(df["time_bin"], df["neg_smooth"], label="부정", color="#d62728")
    ax2.set_title("시간대별 감정 댓글 수 (월드컵 집중 기간)")
    ax2.set_xlabel("시간")
    ax2.set_ylabel("댓글 수")
    ax2.legend()
    overlay_events(
        ax2,
        [
            ("2022-11-28", "가나전 패배 ⚠️", "#d62728"),
            ("2022-12-02", "포르투갈전 승리 🏆", "#2ca02c"),
            ("2022-12-05", "브라질전 패배 ⚠️", "#d62728"),
        ],
    )
    fig2.autofmt_xdate()
    fig2.savefig(os.path.join(out_dir, "analysis_counts_range_kr.png"), bbox_inches="tight", dpi=220)
    plt.close(fig2)


def plot_year_small_multiples(
    csv_annotated: str = "data/processed/comments_with_sentiment.csv",
    out_path: str = "data/processed/analysis_year_panels.png",
    years: Iterable[int] = (2022, 2023, 2024, 2025),
):
    import matplotlib.pyplot as plt

    ensure_korean_font()
    df = pd.read_csv(csv_annotated)
    df["published_at"] = pd.to_datetime(df["published_at"], utc=True, errors="coerce")
    df = df.dropna(subset=["published_at", "sentiment_score"])  # keep only valid rows

    # Aggregate to daily average sentiment score
    def agg_year(y: int) -> pd.DataFrame:
        d = df.loc[df["published_at"].dt.year == y].copy()
        if d.empty:
            return pd.DataFrame({"time_bin": [], "score": []})
        d["time_bin"] = d["published_at"].dt.floor("1D")
        g = d.groupby("time_bin")["sentiment_score"].mean().reset_index()
        g = g.sort_values("time_bin")
        g["score_smooth"] = g["sentiment_score"].rolling(3, min_periods=1).mean()
        return g.rename(columns={"sentiment_score": "score"})

    # Build figure
    import math

    ys = list(years)
    n = len(ys)
    rows = 2
    cols = 2
    fig, axes = plt.subplots(rows, cols, figsize=(12, 6), sharex=False, sharey=True)
    axes = axes.ravel()
    for i, y in enumerate(ys):
        ax = axes[i]
        g = agg_year(y)
        if not g.empty:
            ax.plot(g["time_bin"], g["score_smooth"], color="#1f77b4", label=str(y), linewidth=(2.0 if y == 2022 else 1.5))
        ax.axhline(0.5, color="#999999", linestyle=":", linewidth=1)
        ax.set_title(f"{y}년 평균 감성 점수 (기준선 0.5)")
        ax.set_ylim(0.35, 0.75)
        ax.set_xlabel("시간")
        ax.set_ylabel("평균 감성 점수")
        if y == 2022:
            for spine in ax.spines.values():
                spine.set_linewidth(2)
                spine.set_edgecolor("#d62728")
        fig.autofmt_xdate()

    # Hide any extra axes if years < 4
    for j in range(i + 1, rows * cols):
        fig.delaxes(axes[j])

    fig.suptitle("연도별 평균 감성 점수 소형 패널")
    fig.tight_layout(rect=[0, 0.03, 1, 0.95])
    fig.savefig(out_path, bbox_inches="tight", dpi=220)
    plt.close(fig)


if __name__ == "__main__":
    # Quick entry for manual runs
    plot_focus_range()
    plot_year_small_multiples()

