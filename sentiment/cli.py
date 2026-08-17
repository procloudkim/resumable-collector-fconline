from __future__ import annotations

import argparse
import os
from typing import Optional
from datetime import datetime

import pandas as pd

from .io_utils import load_comments, save_csv, save_sqlite
from .stage_map import VIDEO_STAGE_MAP, STAGE_LABELS
from .lexicon import LexiconScorer
from .mentions import detect_mentions_flags, detect_player_flags
from .plot_fonts import ensure_korean_font
import numpy as np


def _default_in_paths() -> tuple[str, str]:
    return (
        "data/processed/gamst_comments_all.csv",
        "data/processed/gamst_comments_all.db",
    )


def _default_out_paths() -> tuple[str, str]:
    return (
        "data/processed/comments_with_sentiment.csv",
        "data/processed/gamst_comments_scored.db",
    )


def annotate_ns(ns: argparse.Namespace) -> int:
    csv_in, db_in = ns.csv_in, ns.db_in
    if csv_in and os.path.isfile(csv_in):
        df = load_comments(csv_path=csv_in)
    else:
        df = load_comments(db_path=db_in)

    scorer = LexiconScorer.with_seed_and_file(ns.lexicon_file)

    # sentiment scoring and mention flags
    prob_list = []
    label_list = []
    pos_hits = []
    neg_hits = []
    laugh_flags = []
    mk_flags = []
    mp_flags = []

    player_cols: dict[str, list[int]] = {}
    for text in df.get("text", pd.Series([""] * len(df))):
        prob, label, details = scorer.score(str(text))
        prob_list.append(prob)
        label_list.append(label)
        pos_hits.append(details.get("pos_hits", 0))
        neg_hits.append(details.get("neg_hits", 0))
        laugh_flags.append(details.get("laugh", 0))
        flags = detect_mentions_flags(str(text))
        mk_flags.append(flags["mentions_korea"])
        mp_flags.append(flags["mentions_portugal"])
        if ns.per_player_cols:
            pf = detect_player_flags(str(text))
            # initialize lists lazily
            if not player_cols:
                for pname in pf.keys():
                    player_cols[pname] = []
            for pname, v in pf.items():
                player_cols[pname].append(int(v))

    # Stage mapping if absent
    if "stage" not in df.columns and ns.add_stage_map:
        df["stage"] = df["video_id"].map(VIDEO_STAGE_MAP).fillna("unknown")

    df["mentions_korea"] = mk_flags
    df["mentions_portugal"] = mp_flags
    # Attach per-player columns
    if ns.per_player_cols and player_cols:
        for pname, values in player_cols.items():
            df[f"mention_{pname}"] = values
    df["sentiment_score"] = prob_list
    df["sentiment_label"] = label_list
    df["_pos_hits"] = pos_hits
    df["_neg_hits"] = neg_hits
    df["_laugh"] = laugh_flags

    # Save outputs
    save_csv(df, ns.csv_out)
    save_sqlite(df, ns.sqlite_out, table="comments_scored")

    print(f"Annotated {len(df):,} rows -> {ns.csv_out} and {ns.sqlite_out}")
    return 0


def plot_ns(ns: argparse.Namespace) -> int:
    # Load annotated results
    src_csv, src_db = ns.csv_in, ns.db_in
    df = None
    if src_csv and os.path.isfile(src_csv):
        df = pd.read_csv(src_csv)
    elif src_db and os.path.isfile(src_db):
        df = load_comments(db_path=src_db, table="comments_scored")
    else:
        raise FileNotFoundError("Provide annotated csv_in or db_in")

    # Ensure timestamps
    if "published_at" in df.columns:
        df["published_at"] = pd.to_datetime(df["published_at"], utc=True, errors="coerce")
    else:
        raise KeyError("published_at column required for plotting")

    # Time binning
    bin_minutes = ns.bin_minutes
    df["time_bin"] = df["published_at"].dt.floor(f"{bin_minutes}min")

    # Aggregate mean score (overall)
    agg = (
        df.groupby("time_bin")["sentiment_score"].mean().reset_index().sort_values("time_bin")
    )
    # Rolling smoothing
    if ns.rolling > 1:
        agg["score_smooth"] = agg["sentiment_score"].rolling(ns.rolling, min_periods=1).mean()
    else:
        agg["score_smooth"] = agg["sentiment_score"]

    out_dir = ns.out_dir
    os.makedirs(out_dir, exist_ok=True)
    agg_csv = os.path.join(out_dir, "sentiment_timeseries.csv")
    agg.to_csv(agg_csv, index=False)

    # Optional plotting
    try:
        import matplotlib
        import matplotlib.pyplot as plt
        # Try to register a bundled/system Korean font
        ensure_korean_font()

        fig, ax = plt.subplots(figsize=(10, 4))
        ax.plot(agg["time_bin"], agg["score_smooth"], label="전체", color="#1f77b4")
        ax.set_title("시간 경과에 따른 감성 점수 (이동평균)")
        ax.set_xlabel("시간")
        ax.set_ylabel("평균 감성 점수")
        ax.set_ylim(0, 1)
        ax.legend()
        fig.autofmt_xdate()
        png_path = os.path.join(out_dir, "sentiment_timeseries.png")
        plt.savefig(png_path, bbox_inches="tight")
        plt.close(fig)
        print(f"Saved plot -> {png_path}")

        # Mentions overlay plot (if flags exist)
        if {"mentions_korea", "mentions_portugal"}.issubset(df.columns):
            fig2, ax2 = plt.subplots(figsize=(10, 4))
            for label, cond, color in (
                ("대한민국 언급", df["mentions_korea"] == 1, "#2ca02c"),
                ("포르투갈 언급", df["mentions_portugal"] == 1, "#d62728"),
            ):
                sub = (
                    df.loc[cond]
                    .groupby("time_bin")["sentiment_score"]
                    .mean()
                    .reset_index()
                    .sort_values("time_bin")
                )
                sub["score_smooth"] = sub["sentiment_score"].rolling(ns.rolling, min_periods=1).mean()
                ax2.plot(sub["time_bin"], sub["score_smooth"], label=label, color=color)
            ax2.set_title("언급 그룹별 시간대 감성 추이")
            ax2.set_xlabel("시간")
            ax2.set_ylabel("평균 감성 점수")
            ax2.set_ylim(0, 1)
            ax2.legend()
            fig2.autofmt_xdate()
            png_path2 = os.path.join(out_dir, "sentiment_timeseries_mentions.png")
            plt.savefig(png_path2, bbox_inches="tight")
            plt.close(fig2)
            print(f"Saved plot -> {png_path2}")

        # Players overlay plot (if player columns exist)
        players_arg = getattr(ns, "players", "") or ""
        wanted_players = [p.strip() for p in players_arg.split(",") if p.strip()]
        player_cols = [c for c in df.columns if c.startswith("mention_")]
        # Keep only those requested and present
        requested = [p for p in wanted_players if f"mention_{p}" in player_cols]
        if requested:
            figp, axp = plt.subplots(figsize=(10, 4))
            palette = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd", "#8c564b"]
            for idx, pname in enumerate(requested):
                cond = df[f"mention_{pname}"] == 1
                sub = (
                    df.loc[cond]
                    .groupby("time_bin")["sentiment_score"]
                    .mean()
                    .reset_index()
                    .sort_values("time_bin")
                )
                sub["score_smooth"] = sub["sentiment_score"].rolling(ns.rolling, min_periods=1).mean()
                axp.plot(sub["time_bin"], sub["score_smooth"], label=pname, color=palette[idx % len(palette)])
            axp.set_title("선수별 시간대 감성 추이")
            axp.set_xlabel("시간")
            axp.set_ylabel("평균 감성 점수")
            axp.set_ylim(0, 1)
            axp.legend()
            figp.autofmt_xdate()
            png_pathp = os.path.join(out_dir, "sentiment_timeseries_players.png")
            plt.savefig(png_pathp, bbox_inches="tight")
            plt.close(figp)
            print(f"Saved plot -> {png_pathp}")

        # Stage facet plots (one per stage)
        if "stage" in df.columns:
            for stage, g in df.groupby("stage"):
                sub = (
                    g.groupby("time_bin")["sentiment_score"]
                    .mean()
                    .reset_index()
                    .sort_values("time_bin")
                )
                sub["score_smooth"] = sub["sentiment_score"].rolling(ns.rolling, min_periods=1).mean()
                fig3, ax3 = plt.subplots(figsize=(10, 4))
                ax3.plot(sub["time_bin"], sub["score_smooth"], label=str(stage))
                ax3.set_title(f"Sentiment over time — stage={stage}")
                ax3.set_xlabel("Time")
                ax3.set_ylabel("Mean sentiment score")
                # Override titles/labels with Korean professional terms
                label_ko = STAGE_LABELS.get(str(stage), str(stage))
                ax3.set_title(f"스테이지별 시간대 감성 추이 — {label_ko}")
                ax3.set_xlabel("시간")
                ax3.set_ylabel("평균 감성 점수")
                ax3.set_ylim(0, 1)
                fig3.autofmt_xdate()
                png_path3 = os.path.join(out_dir, f"sentiment_timeseries_stage_{stage}.png")
                plt.savefig(png_path3, bbox_inches="tight")
                plt.close(fig3)
                print(f"Saved plot -> {png_path3}")
    except Exception as e:  # noqa: BLE001
        print(f"Plotting skipped ({e}). CSV saved -> {agg_csv}")

    return 0


def report_ns(ns: argparse.Namespace) -> int:
    # Load annotated results (CSV preferred)
    src_csv, src_db = ns.csv_in, ns.db_in
    if src_csv and os.path.isfile(src_csv):
        df = pd.read_csv(src_csv)
    elif src_db and os.path.isfile(src_db):
        df = load_comments(db_path=src_db, table="comments_scored")
    else:
        raise FileNotFoundError("Provide annotated csv_in or db_in")

    # Ensure expected cols
    if "sentiment_label" not in df.columns:
        raise KeyError("sentiment_label not found. Run annotate first.")
    if "sentiment_score" not in df.columns:
        raise KeyError("sentiment_score not found. Run annotate first.")
    if "published_at" in df.columns:
        df["published_at"] = pd.to_datetime(df["published_at"], utc=True, errors="coerce")
    if "like_count" in df.columns:
        df["like_count"] = pd.to_numeric(df["like_count"], errors="coerce").fillna(0).astype(int)
    else:
        df["like_count"] = 0

    out_dir = ns.out_dir
    os.makedirs(out_dir, exist_ok=True)

    def _summarize(grouped: pd.core.groupby.generic.DataFrameGroupBy) -> pd.DataFrame:
        stats = grouped.apply(
            lambda g: pd.Series(
                {
                    "n": len(g),
                    "pos": int((g["sentiment_label"] == "positive").sum()),
                    "neg": int((g["sentiment_label"] == "negative").sum()),
                    "neu": int((g["sentiment_label"] == "neutral").sum()),
                    "pos_ratio": float((g["sentiment_label"] == "positive").mean()),
                    "mean_score": float(g["sentiment_score"].mean()),
                    "mean_likes": float(g["like_count"].mean()),
                }
            )
        ).reset_index()
        return stats

    # Overall summary
    overall = _summarize(df.assign(overall="all").groupby("overall"))
    overall.to_csv(os.path.join(out_dir, "summary_overall.csv"), index=False)

    # Stage summary if available
    if "stage" in df.columns:
        stage = _summarize(df.groupby("stage"))
        stage.to_csv(os.path.join(out_dir, "summary_stage.csv"), index=False)

    # Mentions summary
    has_mk = "mentions_korea" in df.columns
    has_mp = "mentions_portugal" in df.columns
    if has_mk or has_mp:
        parts = []
        if has_mk:
            parts.append(df.assign(group=df["mentions_korea"].apply(lambda x: "korea" if x == 1 else "non_korea")))
        if has_mp:
            parts.append(df.assign(group=df["mentions_portugal"].apply(lambda x: "portugal" if x == 1 else "non_portugal")))
        grp = pd.concat(parts, ignore_index=True) if parts else df
        summ = _summarize(grp.groupby("group"))
        summ.to_csv(os.path.join(out_dir, "summary_mentions.csv"), index=False)

    # Cross: stage x mentions
    if (has_mk or has_mp) and "stage" in df.columns:
        frames = []
        if has_mk:
            frames.append(
                df.assign(group=df["mentions_korea"].apply(lambda x: "korea" if x == 1 else "non_korea"))
                .groupby(["stage", "group"])
            )
        if has_mp:
            frames.append(
                df.assign(group=df["mentions_portugal"].apply(lambda x: "portugal" if x == 1 else "non_portugal"))
                .groupby(["stage", "group"])
            )
        out = []
        for g in frames:
            out.append(_summarize(g))
        combined = pd.concat(out, ignore_index=True)
        combined.to_csv(os.path.join(out_dir, "summary_stage_mentions.csv"), index=False)

    # Weighted by likes (stage)
    if "stage" in df.columns:
        def _weighted_mean(x):
            w = x["like_count"].astype(float)
            s = x["sentiment_score"].astype(float)
            if w.sum() == 0:
                return float(s.mean())
            return float((s * (w + 1)).sum() / (w + 1).sum())  # add-1 smoothing

        w = df.groupby("stage").apply(
            lambda g: pd.Series(
                {
                    "n": len(g),
                    "weighted_score": _weighted_mean(g),
                }
            )
        ).reset_index()
        w.to_csv(os.path.join(out_dir, "summary_stage_weighted.csv"), index=False)

    # Players summary if per-player columns exist
    player_cols = [c for c in df.columns if c.startswith("mention_")]
    if player_cols:
        # overall per player
        recs = []
        for col in player_cols:
            pname = col.replace("mention_", "")
            g = df.loc[df[col] == 1]
            if len(g) == 0:
                continue
            summ = _summarize(g.assign(player=pname).groupby("player"))
            recs.append(summ)
        if recs:
            all_players = pd.concat(recs, ignore_index=True)
            all_players.to_csv(os.path.join(out_dir, "summary_players.csv"), index=False)

        # stage x player
        recs = []
        if "stage" in df.columns:
            for col in player_cols:
                pname = col.replace("mention_", "")
                g = df.loc[df[col] == 1]
                if len(g) == 0:
                    continue
                summ = _summarize(g.assign(player=pname).groupby(["stage", "player"]))
                recs.append(summ)
            if recs:
                sp = pd.concat(recs, ignore_index=True)
                sp.to_csv(os.path.join(out_dir, "summary_stage_players.csv"), index=False)

    print(f"Saved summaries to {out_dir}")
    return 0


def _parse_utc(s: Optional[str]) -> Optional[pd.Timestamp]:
    if not s:
        return None
    try:
        # Let pandas parse, force UTC
        ts = pd.to_datetime(s, utc=True)
        return ts
    except Exception:
        return None


def slice_ns(ns: argparse.Namespace) -> int:
    df = pd.read_csv(ns.csv_in)
    if "published_at" not in df.columns:
        raise KeyError("published_at required in annotated CSV")
    df["published_at"] = pd.to_datetime(df["published_at"], utc=True, errors="coerce")
    start = _parse_utc(ns.start_utc)
    end = _parse_utc(ns.end_utc)
    if start is None or end is None:
        raise ValueError("Invalid start/end UTC datetime")
    mask = (df["published_at"] >= start) & (df["published_at"] <= end)
    out = df.loc[mask].copy()
    os.makedirs(os.path.dirname(ns.out), exist_ok=True)
    out.to_csv(ns.out, index=False)
    print(f"Saved slice {len(out):,} rows -> {ns.out}")
    return 0


def _agg_time(df: pd.DataFrame, bin_minutes: int, rolling: int) -> pd.DataFrame:
    df = df.copy()
    if "published_at" not in df.columns:
        raise KeyError("published_at required")
    df["published_at"] = pd.to_datetime(df["published_at"], utc=True, errors="coerce")
    df["time_bin"] = df["published_at"].dt.floor(f"{bin_minutes}min")
    # compute counts
    g = df.groupby("time_bin")
    agg = pd.DataFrame({
        "pos": g.apply(lambda x: (x["sentiment_label"] == "positive").sum()),
        "neg": g.apply(lambda x: (x["sentiment_label"] == "negative").sum()),
        "neu": g.apply(lambda x: (x["sentiment_label"] == "neutral").sum()),
    }).reset_index().sort_values("time_bin")
    total = (agg["pos"] + agg["neg"] + agg["neu"]).replace(0, pd.NA)
    agg["pos_ratio"] = (agg["pos"] / total).astype(float)
    # rolling smoothing
    if rolling > 1:
        for col in ("pos_ratio", "pos", "neg"):
            agg[f"{col}_smooth"] = agg[col].rolling(rolling, min_periods=1).mean()
    else:
        for col in ("pos_ratio", "pos", "neg"):
            agg[f"{col}_smooth"] = agg[col]
    return agg


def analyze_ns(ns: argparse.Namespace) -> int:
    ensure_korean_font()
    df = pd.read_csv(ns.csv_in)
    if "published_at" not in df.columns or "sentiment_label" not in df.columns:
        raise KeyError("annotated CSV must include published_at and sentiment_label")
    df["published_at"] = pd.to_datetime(df["published_at"], utc=True, errors="coerce")
    start = _parse_utc(ns.start_utc)
    end = _parse_utc(ns.end_utc)
    if start is not None:
        df = df.loc[df["published_at"] >= start]
    if end is not None:
        df = df.loc[df["published_at"] <= end]

    os.makedirs(ns.out_dir, exist_ok=True)

    try:
        import matplotlib.pyplot as plt  # type: ignore
        have_plt = True
    except ModuleNotFoundError:
        have_plt = False

    def _plot_and_save(agg: pd.DataFrame, tag: str):
        if not have_plt:
            print("Matplotlib 미설치로 그래프 생성을 건너뜁니다. `pip install matplotlib` 후 재실행하세요.")
            return
        # pos ratio
        fig, ax = plt.subplots(figsize=(10, 4))
        ax.plot(agg["time_bin"], agg["pos_ratio_smooth"], label="긍정 비율", color="#2ca02c")
        ax.set_title(f"시간대별 긍정 비율 ({tag})")
        ax.set_xlabel("시간")
        ax.set_ylabel("긍정 비율")
        ax.set_ylim(0, 1)
        fig.autofmt_xdate()
        out_png = os.path.join(ns.out_dir, f"analysis_posratio_{tag}.png")
        fig.savefig(out_png, bbox_inches="tight", dpi=220)
        plt.close(fig)

        # counts
        fig2, ax2 = plt.subplots(figsize=(10, 4))
        ax2.plot(agg["time_bin"], agg["pos_smooth"], label="긍정", color="#2ca02c")
        ax2.plot(agg["time_bin"], agg["neg_smooth"], label="부정", color="#d62728")
        ax2.set_title(f"시간대별 감정 댓글 수 ({tag})")
        ax2.set_xlabel("시간")
        ax2.set_ylabel("댓글 수")
        ax2.legend()
        fig2.autofmt_xdate()
        out_png2 = os.path.join(ns.out_dir, f"analysis_counts_{tag}.png")
        fig2.savefig(out_png2, bbox_inches="tight", dpi=220)
        plt.close(fig2)

    # overall or per year
    if ns.per_year:
        years = sorted({ts.year for ts in df["published_at"].dropna()})
        for y in years:
            dfy = df.loc[df["published_at"].dt.year == y]
            agg = _agg_time(dfy, ns.bin_minutes, ns.rolling)
            csv_path = os.path.join(ns.out_dir, f"analysis_timeseries_{y}.csv")
            agg.to_csv(csv_path, index=False)
            _plot_and_save(agg, str(y))
    else:
        agg = _agg_time(df, ns.bin_minutes, ns.rolling)
        csv_path = os.path.join(ns.out_dir, "analysis_timeseries_range.csv")
        agg.to_csv(csv_path, index=False)
        tag = "range"
        if start is not None and end is not None:
            tag = f"{start.date()}_{end.date()}"
        _plot_and_save(agg, tag)
    print(f"Saved analysis to {ns.out_dir}")
    return 0


def report_players_ns(ns: argparse.Namespace) -> int:
    ensure_korean_font()
    df = pd.read_csv(ns.csv_in)
    # require per-player columns
    player_cols = [c for c in df.columns if c.startswith("mention_")]
    if not player_cols:
        raise RuntimeError("No per-player columns found. Re-run annotate with --per-player-cols.")
    if "stage" not in df.columns:
        raise RuntimeError("stage column required for pre/post comparison. Use --add-stage-map when annotating.")
    df["published_at"] = pd.to_datetime(df["published_at"], utc=True, errors="coerce")
    os.makedirs(ns.out_dir, exist_ok=True)

    try:
        import matplotlib.pyplot as plt  # type: ignore
        have_plt = True
    except ModuleNotFoundError:
        have_plt = False

    # Build per-player dataframe
    recs = []
    for col in player_cols:
        pname = col.replace("mention_", "")
        g = df.loc[df[col] == 1]
        if len(g) == 0:
            continue
        # pre vs post pos_ratio and weighted score
        def _weighted_mean(x):
            w = pd.to_numeric(x.get("like_count", 0), errors="coerce").fillna(0).astype(float)
            s = pd.to_numeric(x.get("sentiment_score", 0.5), errors="coerce").astype(float)
            if (w + 1).sum() == 0:
                return float(s.mean())
            return float((s * (w + 1)).sum() / (w + 1).sum())

        grp = g.groupby("stage")
        pos_ratio = grp.apply(lambda x: (x["sentiment_label"] == "positive").mean())
        wscore = grp.apply(_weighted_mean)
        recs.append({
            "player": pname,
            "pos_ratio_pre": float(pos_ratio.get("pre", float("nan"))),
            "pos_ratio_post": float(pos_ratio.get("post", float("nan"))),
            "pos_ratio_diff": float(pos_ratio.get("post", float("nan")) - pos_ratio.get("pre", float("nan"))) if pd.notna(pos_ratio.get("post")) and pd.notna(pos_ratio.get("pre")) else float("nan"),
            "wscore_pre": float(wscore.get("pre", float("nan"))),
            "wscore_post": float(wscore.get("post", float("nan"))),
            "wscore_diff": float(wscore.get("post", float("nan")) - wscore.get("pre", float("nan"))) if pd.notna(wscore.get("post")) and pd.notna(wscore.get("pre")) else float("nan"),
        })

    comp = pd.DataFrame(recs)
    comp_path = os.path.join(ns.out_dir, "player_stage_comparison.csv")
    comp.to_csv(comp_path, index=False)

    # Plots
    pos_png = w_png = None
    if have_plt:
        # 1) pos_ratio diff bar
        comp_sorted = comp.sort_values("pos_ratio_diff", ascending=False).dropna(subset=["pos_ratio_diff"])
        fig, ax = plt.subplots(figsize=(8, max(3, 0.6 * len(comp_sorted))))
        ax.barh(comp_sorted["player"], comp_sorted["pos_ratio_diff"], color="#1f77b4")
        ax.set_title("선수별 긍정 비율 차이 (경기 후 - 경기 전)")
        ax.set_xlabel("차이 (후 - 전)")
        fig.tight_layout()
        pos_png = os.path.join(ns.out_dir, "player_posratio_pre_post.png")
        fig.savefig(pos_png, bbox_inches="tight", dpi=220)
        plt.close(fig)

        # 2) weighted score pre vs post grouped bars
        comp2 = comp.dropna(subset=["wscore_pre", "wscore_post"]).copy()
        fig2, ax2 = plt.subplots(figsize=(8, max(3, 0.6 * len(comp2))))
        y = comp2["player"]
        ax2.barh(y, comp2["wscore_pre"], label="전", color="#ff7f0e", alpha=0.8)
        ax2.barh(y, comp2["wscore_post"], label="후", color="#2ca02c", alpha=0.8)
        ax2.set_title("선수별 좋아요 가중 감성 점수")
        ax2.set_xlabel("가중 감성 점수 (0-1)")
        ax2.legend()
        fig2.tight_layout()
        w_png = os.path.join(ns.out_dir, "player_weighted_score_pre_post.png")
        fig2.savefig(w_png, bbox_inches="tight", dpi=220)
        plt.close(fig2)
    else:
        print("Matplotlib 미설치로 선수별 그래프 생성을 건너뜁니다. `pip install matplotlib` 후 재실행하세요.")

    # Report
    if ns.format == "md":
        md_path = os.path.join(ns.out_dir, "player_report.md")
        with open(md_path, "w", encoding="utf-8") as f:
            f.write("# 선수별 비교 분석 보고서\n\n")
            f.write("## 요약\n")
            f.write(f"- 비교표: `{os.path.basename(comp_path)}`\n")
            if pos_png and w_png:
                f.write(f"- 이미지: `{os.path.basename(pos_png)}`, `{os.path.basename(w_png)}`\n\n")
            else:
                f.write("- 이미지: matplotlib 미설치로 생성되지 않았습니다. `pip install matplotlib` 후 재실행하세요.\n\n")
            if pos_png:
                f.write("## 긍정 비율 차이 (경기 후 - 경기 전)\n\n")
                f.write(f"![pos_ratio]({os.path.basename(pos_png)})\n\n")
            if w_png:
                f.write("## 좋아요 가중 평균 감성 점수\n\n")
                f.write(f"![weighted]({os.path.basename(w_png)})\n")
        print(f"Saved report -> {md_path}")
    else:
        # Simple HTML
        html_path = os.path.join(ns.out_dir, "player_report.html")
        with open(html_path, "w", encoding="utf-8") as f:
            f.write("<html><head><meta charset='utf-8'><title>선수별 비교 분석 보고서</title></head><body>\n")
            f.write("<h1>선수별 비교 분석 보고서</h1>\n")
            f.write(f"<p>비교표: {os.path.basename(comp_path)}</p>\n")
            if pos_png:
                f.write(f"<h2>긍정 비율 차이 (경기 후 - 경기 전)</h2><img src='{os.path.basename(pos_png)}' style='max-width:100%'>\n")
            if w_png:
                f.write(f"<h2>좋아요 가중 평균 감정 점수</h2><img src='{os.path.basename(w_png)}' style='max-width:100%'>\n")
            if not (pos_png and w_png):
                f.write("<p>이미지: matplotlib 미설치로 생성되지 않았습니다. `pip install matplotlib` 후 재실행하세요.</p>")
            f.write("</body></html>")
        print(f"Saved report -> {html_path}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="sentiment",
        description="KR sentiment analysis for YouTube comments",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    # annotate
    a = sub.add_parser("annotate", help="Annotate comments with mentions + sentiment")
    csv_in, db_in = _default_in_paths()
    csv_out, sqlite_out = _default_out_paths()
    a.add_argument("--csv-in", default=csv_in, help="Input CSV path (raw comments)")
    a.add_argument("--db-in", default=db_in, help="Input SQLite path (raw comments)")
    a.add_argument("--csv-out", default=csv_out, help="Output CSV path (annotated)")
    a.add_argument("--sqlite-out", default=sqlite_out, help="Output SQLite path (annotated)")
    a.add_argument("--lexicon-file", default="config/slang_lexicon.txt", help="Optional external lexicon file")
    a.add_argument("--add-stage-map", action="store_true", help="Add stage column via built-in video_id mapping if missing")
    a.add_argument("--per-player-cols", action="store_true", help="Add per-player mention columns (e.g., mention_손흥민, mention_호날두)")
    a.set_defaults(func=annotate_ns)

    # plot
    pl = sub.add_parser("plot", help="Aggregate and plot sentiment over time")
    pl.add_argument("--csv-in", default=csv_out, help="Annotated CSV path")
    pl.add_argument("--db-in", default=sqlite_out, help="Annotated SQLite path")
    pl.add_argument("--out-dir", default="data/processed", help="Output directory for plots/aggregates")
    pl.add_argument("--bin-minutes", type=int, default=15, help="Time bin size in minutes")
    pl.add_argument("--rolling", type=int, default=3, help="Rolling window size (bins)")
    pl.add_argument("--players", default="손흥민,호날두", help="Comma-separated player names to overlay if per-player columns exist")
    pl.set_defaults(func=plot_ns)

    # slice by date range (UTC) and save subset
    sl = sub.add_parser("slice", help="Filter annotated comments by UTC date range and save")
    sl.add_argument("--csv-in", default=csv_out, help="Annotated CSV path")
    sl.add_argument("--start-utc", required=True, help="Start datetime UTC (e.g., 2022-11-25 or 2022-11-25T00:00:00Z)")
    sl.add_argument("--end-utc", required=True, help="End datetime UTC (inclusive)")
    sl.add_argument("--out", default="data/processed/comments_with_sentiment_slice.csv", help="Output CSV path for slice")
    sl.set_defaults(func=slice_ns)

    # analyze time trends (pos/neg) with optional range and per-year splits
    an = sub.add_parser("analyze", help="Analyze time trends: pos/neg ratio and counts")
    an.add_argument("--csv-in", default=csv_out, help="Annotated CSV path")
    an.add_argument("--out-dir", default="data/processed", help="Output directory")
    an.add_argument("--start-utc", default=None, help="Optional start datetime UTC")
    an.add_argument("--end-utc", default=None, help="Optional end datetime UTC (inclusive)")
    an.add_argument("--bin-minutes", type=int, default=15, help="Time bin size in minutes")
    an.add_argument("--rolling", type=int, default=3, help="Rolling window size (bins)")
    an.add_argument("--per-year", action="store_true", help="Split by published year and output per-year series")
    an.add_argument("--add-worldcup-events", action="store_true", help="Overlay 2022 World Cup key events on plots")
    an.add_argument("--small-multiples", action="store_true", help="When --per-year, also save a 2x2 year panel figure")
    an.set_defaults(func=analyze_ns)

    # player report with visuals (pre vs post)
    pr = sub.add_parser("report-players", help="Generate player comparison report (pre vs post) with plots")
    pr.add_argument("--csv-in", default=csv_out, help="Annotated CSV path")
    pr.add_argument("--out-dir", default="data/processed", help="Output directory")
    pr.add_argument("--format", choices=["md", "html"], default="md", help="Report format")
    pr.set_defaults(func=report_players_ns)

    # report
    rp = sub.add_parser("report", help="Summarize sentiment by stage and mentions")
    rp.add_argument("--csv-in", default=csv_out, help="Annotated CSV path")
    rp.add_argument("--db-in", default=sqlite_out, help="Annotated SQLite path (table=comments_scored)")
    rp.add_argument("--out-dir", default="data/processed", help="Output directory for summary CSVs")
    rp.set_defaults(func=report_ns)

    return p


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    ns = parser.parse_args(argv)
    return ns.func(ns)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
