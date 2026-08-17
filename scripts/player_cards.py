from __future__ import annotations

import os
from typing import Dict, List, Tuple

import pandas as pd
import numpy as np

from sentiment.plot_fonts import ensure_korean_font


def _weighted_mean(df: pd.DataFrame) -> float:
    w = pd.to_numeric(df.get("like_count", 0), errors="coerce").fillna(0).astype(float)
    s = pd.to_numeric(df.get("sentiment_score", 0.5), errors="coerce").astype(float)
    if (w + 1).sum() == 0:
        return float(s.mean())
    return float((s * (w + 1)).sum() / (w + 1).sum())


def compute_player_metrics(df: pd.DataFrame, player: str) -> Dict[str, float]:
    col = f"mention_{player}"
    if col not in df.columns:
        raise KeyError(f"Column {col} not found. Re-run annotate with --per-player-cols")
    g = df.loc[df[col] == 1].copy()
    if g.empty:
        return {
            "pos_ratio_pre": np.nan,
            "pos_ratio_post": np.nan,
            "wscore_pre": np.nan,
            "wscore_post": np.nan,
        }
    if "stage" not in g.columns:
        raise KeyError("stage column required. Annotate with --add-stage-map")
    grp = g.groupby("stage")
    pos_ratio = grp.apply(lambda x: (x["sentiment_label"] == "positive").mean())
    wscore = grp.apply(_weighted_mean)
    return {
        "pos_ratio_pre": float(pos_ratio.get("pre", np.nan)),
        "pos_ratio_post": float(pos_ratio.get("post", np.nan)),
        "wscore_pre": float(wscore.get("pre", np.nan)),
        "wscore_post": float(wscore.get("post", np.nan)),
    }


def draw_player_card(ax, name: str, m: Dict[str, float]) -> None:
    import matplotlib.pyplot as plt

    ensure_korean_font()
    ax.axis("off")
    # Title
    ax.text(0.02, 0.95, name, fontsize=14, fontweight="bold", va="top")

    # Bars: pre/post positive ratio
    pre = m.get("pos_ratio_pre", np.nan)
    post = m.get("pos_ratio_post", np.nan)
    wpre = m.get("wscore_pre", np.nan)
    wpost = m.get("wscore_post", np.nan)

    # Left bar pair (pos ratio)
    ax.bar([0.15], [pre * 100 if pd.notna(pre) else 0], width=0.1, color="#1f77b4", label="전")
    ax.bar([0.30], [post * 100 if pd.notna(post) else 0], width=0.1, color="#ff7f0e", label="후")
    ax.text(0.15, (pre * 100 if pd.notna(pre) else 0) + 2, f"전 {pre*100:.1f}%" if pd.notna(pre) else "전 -", ha="center", fontsize=9)
    ax.text(0.30, (post * 100 if pd.notna(post) else 0) + 2, f"후 {post*100:.1f}%" if pd.notna(post) else "후 -", ha="center", fontsize=9)
    # Diff arrow for pos ratio
    if pd.notna(pre) and pd.notna(post):
        diff = (post - pre) * 100
        arrow = "↑" if diff >= 0 else "↓"
        color = "#2ca02c" if diff >= 0 else "#d62728"
        ax.text(0.225, 95, f"{arrow} {diff:+.1f}%p", color=color, ha="center", fontsize=11)
    ax.text(0.225, 105, "긍정 비율", ha="center", fontsize=10, fontweight="bold")

    # Right bar pair (likes-weighted score)
    ax.bar([0.65], [wpre * 100 if pd.notna(wpre) else 0], width=0.1, color="#1f77b4")
    ax.bar([0.80], [wpost * 100 if pd.notna(wpost) else 0], width=0.1, color="#ff7f0e")
    ax.text(0.65, (wpre * 100 if pd.notna(wpre) else 0) + 2, f"전 {wpre*100:.1f}%" if pd.notna(wpre) else "전 -", ha="center", fontsize=9)
    ax.text(0.80, (wpost * 100 if pd.notna(wpost) else 0) + 2, f"후 {wpost*100:.1f}%" if pd.notna(wpost) else "후 -", ha="center", fontsize=9)
    if pd.notna(wpre) and pd.notna(wpost):
        wdiff = (wpost - wpre) * 100
        arrow2 = "👍 ↑" if wdiff >= 0 else "↓"
        color2 = "#2ca02c" if wdiff >= 0 else "#d62728"
        ax.text(0.725, 95, f"{arrow2} {wdiff:+.1f}%p", color=color2, ha="center", fontsize=11)
    ax.text(0.725, 105, "좋아요 가중 점수", ha="center", fontsize=10, fontweight="bold")

    # Frame and y-limits
    ax.set_ylim(0, 110)
    for spine in ax.spines.values():
        spine.set_visible(True)
        spine.set_linewidth(0.5)


def generate_player_cards(
    annotated_csv: str = "data/processed/comments_with_sentiment.csv",
    players: List[str] | None = None,
    out_dir: str = "data/processed/cards",
) -> List[str]:
    import matplotlib.pyplot as plt

    os.makedirs(out_dir, exist_ok=True)
    df = pd.read_csv(annotated_csv)
    if players is None:
        players = ["손흥민", "황희찬", "김영권", "호날두"]

    file_paths: List[str] = []
    # Individual cards
    for p in players:
        metrics = compute_player_metrics(df, p)
        fig, ax = plt.subplots(figsize=(4.5, 3.2))
        draw_player_card(ax, p, metrics)
        fig.tight_layout()
        path = os.path.join(out_dir, f"player_card_{p}.png")
        fig.savefig(path, bbox_inches="tight", dpi=220)
        plt.close(fig)
        file_paths.append(path)

    # Composite grid
    n = len(players)
    rows = 2
    cols = 2
    fig, axes = plt.subplots(rows, cols, figsize=(10, 6))
    axes = axes.ravel()
    for i, p in enumerate(players[: rows * cols]):
        m = compute_player_metrics(df, p)
        draw_player_card(axes[i], p, m)
    # Hide any extra axes
    for j in range(i + 1, rows * cols):
        axes[j].axis("off")
    fig.suptitle("선수별 카드 요약 (전/후 긍정률 · 좋아요 가중 점수)")
    fig.tight_layout(rect=[0, 0.03, 1, 0.95])
    grid_path = os.path.join(out_dir, "player_cards_grid.png")
    fig.savefig(grid_path, bbox_inches="tight", dpi=220)
    plt.close(fig)
    file_paths.append(grid_path)
    return file_paths


if __name__ == "__main__":
    paths = generate_player_cards()
    print("Saved:")
    for p in paths:
        print(" -", p)

