from __future__ import annotations

import os
import sys
import pandas as pd
import numpy as np


def load_comments(path: str) -> pd.DataFrame:
    if not os.path.isfile(path):
        raise FileNotFoundError(f"comments csv not found: {path}")
    df = pd.read_csv(path)
    # ensure expected columns
    required = [
        "video_id",
        "video_title",
        "comment_id",
        "text",
        "like_count",
        "published_at",
        "is_reply",
        "sentiment_score",
        "sentiment_label",
    ]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise KeyError(f"comments csv missing columns: {missing}")
    # normalize types
    df["like_count"] = pd.to_numeric(df.get("like_count", 0), errors="coerce").fillna(0).astype(float)
    if "published_at" in df.columns:
        df["published_at"] = pd.to_datetime(df["published_at"], utc=True, errors="coerce")
    return df


def load_meta(path: str) -> pd.DataFrame:
    if not os.path.isfile(path):
        raise FileNotFoundError(f"meta csv not found: {path}")
    meta = pd.read_csv(path)
    required = [
        "video_id",
        "stage",
        "channel",
        "channel_type",
        "title",
        "posted_date",
        "views",
        "likes",
        "comment_count",
        "observation_date",
    ]
    missing = [c for c in required if c not in meta.columns]
    if missing:
        raise KeyError(f"meta csv missing columns: {missing}")
    meta["views"] = pd.to_numeric(meta["views"], errors="coerce").fillna(0).astype(float)
    meta["likes"] = pd.to_numeric(meta["likes"], errors="coerce").fillna(0).astype(float)
    meta["comment_count"] = pd.to_numeric(meta["comment_count"], errors="coerce").fillna(0).astype(float)
    if "posted_date" in meta.columns:
        meta["posted_date"] = pd.to_datetime(meta["posted_date"], errors="coerce")
    return meta


def summarize_by_video(df: pd.DataFrame, meta: pd.DataFrame) -> pd.DataFrame:
    # convenience flags
    df = df.copy()
    df["is_pos"] = (df["sentiment_label"] == "positive").astype(int)
    df["is_neg"] = (df["sentiment_label"] == "negative").astype(int)
    df["is_neu"] = (df["sentiment_label"] == "neutral").astype(int)
    for col in ("mentions_korea", "mentions_portugal", "_laugh"):
        if col not in df.columns:
            df[col] = 0

    def _wscore(g: pd.DataFrame) -> float:
        s = pd.to_numeric(g.get("sentiment_score", 0.5), errors="coerce").fillna(0.5).astype(float)
        w = pd.to_numeric(g.get("like_count", 0), errors="coerce").fillna(0).astype(float)
        return float((s * (w + 1)).sum() / (w + 1).sum()) if len(g) else np.nan

    grp = df.groupby(["video_id", "video_title"], dropna=False)
    out = grp.apply(
        lambda g: pd.Series(
            {
                "n_comments": int(len(g)),
                "n_replies": int(pd.to_numeric(g.get("is_reply", 0), errors="coerce").fillna(0).astype(int).sum()),
                "pos_ratio": float(g["is_pos"].mean()),
                "neg_ratio": float(g["is_neg"].mean()),
                "neu_ratio": float(g["is_neu"].mean()),
                "mean_sentiment": float(pd.to_numeric(g["sentiment_score"], errors="coerce").fillna(0.5).mean()),
                "wscore_like_weighted": _wscore(g),
                "mean_like_count": float(g["like_count"].mean()),
                "mentions_korea_rate": float(pd.to_numeric(g["mentions_korea"], errors="coerce").fillna(0).mean()),
                "mentions_portugal_rate": float(pd.to_numeric(g["mentions_portugal"], errors="coerce").fillna(0).mean()),
                "laugh_rate": float(pd.to_numeric(g["_laugh"], errors="coerce").fillna(0).mean()),
            }
        )
    ).reset_index()

    merged = out.merge(meta, how="left", on="video_id")
    # Derived metrics
    merged["comments_per_100k_views"] = np.where(
        merged["views"] > 0, merged["n_comments"] / merged["views"] * 100000.0, np.nan
    )
    merged["video_like_ratio"] = np.where(
        merged["views"] > 0, merged["likes"] / merged["views"], np.nan
    )
    # Keep a concise column order
    cols = [
        "video_id",
        "video_title",
        "stage",
        "channel",
        "channel_type",
        "title",
        "posted_date",
        "views",
        "likes",
        "comment_count",
        "n_comments",
        "n_replies",
        "pos_ratio",
        "neg_ratio",
        "neu_ratio",
        "mean_sentiment",
        "wscore_like_weighted",
        "mean_like_count",
        "mentions_korea_rate",
        "mentions_portugal_rate",
        "laugh_rate",
        "comments_per_100k_views",
        "video_like_ratio",
        "observation_date",
        "notes",
    ]
    cols = [c for c in cols if c in merged.columns]
    return merged[cols]


def summarize_by_channel_type(video_summary: pd.DataFrame) -> pd.DataFrame:
    # Micro-averages by expanding back to counts
    vs = video_summary.copy()
    vs["pos_count"] = (vs["pos_ratio"] * vs["n_comments"]).fillna(0.0)
    vs["neg_count"] = (vs["neg_ratio"] * vs["n_comments"]).fillna(0.0)
    vs["neu_count"] = (vs["neu_ratio"] * vs["n_comments"]).fillna(0.0)
    grp = vs.groupby("channel_type", dropna=False)
    out = grp.apply(
        lambda g: pd.Series(
            {
                "videos": int(len(g)),
                "total_comments": int(g["n_comments"].sum()),
                "pos_ratio": float(g["pos_count"].sum() / g["n_comments"].sum()) if g["n_comments"].sum() else np.nan,
                "neg_ratio": float(g["neg_count"].sum() / g["n_comments"].sum()) if g["n_comments"].sum() else np.nan,
                "neu_ratio": float(g["neu_count"].sum() / g["n_comments"].sum()) if g["n_comments"].sum() else np.nan,
                "mean_wscore": float(np.average(g["wscore_like_weighted"], weights=g["n_comments"])) if g["n_comments"].sum() else np.nan,
                "sum_views": float(g["views"].sum()),
                "sum_likes": float(g["likes"].sum()),
                "comments_per_100k_views": float((g["n_comments"].sum() / g["views"].sum()) * 100000.0) if g["views"].sum() else np.nan,
                "video_like_ratio": float(g["likes"].sum() / g["views"].sum()) if g["views"].sum() else np.nan,
            }
        )
    ).reset_index()
    return out


def summarize_stage_channel_type(video_summary: pd.DataFrame) -> pd.DataFrame:
    vs = video_summary.copy()
    vs["pos_count"] = (vs["pos_ratio"] * vs["n_comments"]).fillna(0.0)
    vs["neg_count"] = (vs["neg_ratio"] * vs["n_comments"]).fillna(0.0)
    vs["neu_count"] = (vs["neu_ratio"] * vs["n_comments"]).fillna(0.0)
    grp = vs.groupby(["stage", "channel_type"], dropna=False)
    out = grp.apply(
        lambda g: pd.Series(
            {
                "videos": int(len(g)),
                "total_comments": int(g["n_comments"].sum()),
                "pos_ratio": float(g["pos_count"].sum() / g["n_comments"].sum()) if g["n_comments"].sum() else np.nan,
                "mean_wscore": float(np.average(g["wscore_like_weighted"], weights=g["n_comments"])) if g["n_comments"].sum() else np.nan,
                "comments_per_100k_views": float((g["n_comments"].sum() / g["views"].sum()) * 100000.0) if g["views"].sum() else np.nan,
            }
        )
    ).reset_index()
    return out


def main(argv: list[str]) -> int:
    # Defaults
    comments_csv = os.getenv("COMMENTS_CSV", "data_check/comments_with_sentiment_copy.csv")
    meta_csv = os.getenv("META_CSV", "config/video_meta_manual.csv")
    out_dir = os.getenv("OUT_DIR", "data/reports")
    if len(argv) >= 2:
        comments_csv = argv[1]
    if len(argv) >= 3:
        meta_csv = argv[2]
    os.makedirs(out_dir, exist_ok=True)

    comments = load_comments(comments_csv)
    meta = load_meta(meta_csv)

    # Restrict to the 11 meta-listed videos
    vid_set = set(meta["video_id"].tolist())
    comments_sub = comments.loc[comments["video_id"].isin(vid_set)].copy()
    if comments_sub.empty:
        print("No comments matched the provided meta video_id list.")
        return 0

    video_summary = summarize_by_video(comments_sub, meta)
    channel_summary = summarize_by_channel_type(video_summary)
    stage_channel_summary = summarize_stage_channel_type(video_summary)

    p1 = os.path.join(out_dir, "comments_meta_video_summary.csv")
    p2 = os.path.join(out_dir, "comments_meta_channel_type_summary.csv")
    p3 = os.path.join(out_dir, "comments_meta_stage_channel_type_summary.csv")
    video_summary.to_csv(p1, index=False)
    channel_summary.to_csv(p2, index=False)
    stage_channel_summary.to_csv(p3, index=False)
    print(f"Saved:\n - {p1}\n - {p2}\n - {p3}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

