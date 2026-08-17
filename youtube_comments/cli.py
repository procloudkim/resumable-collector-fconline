from __future__ import annotations

import argparse
import sys
from typing import List, Optional, Sequence

from .client import build_youtube_client, load_env_if_possible
from .fetcher import Comment, fetch_comments, get_video_metadata
from .filtering import filter_spam
from .sampling import balanced_pair, sample_list
from .storage import init_db, save_csv, upsert_comments
from .utils import get_env_api_key, parse_video_id


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Collect YouTube comments from specific videos (Gamst).",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument(
        "--videos",
        nargs="+",
        required=True,
        help="One or more YouTube video IDs or URLs (CSV or space separated)",
    )
    p.add_argument("--api-key", help="YouTube API key (overrides env)")
    p.add_argument(
        "--order",
        default="time",
        choices=["time", "relevance"],
        help="API fetch order for comments",
    )
    p.add_argument(
        "--balanced",
        action="store_true",
        help="Balance per-video sample size to the smaller video's comment count",
    )
    p.add_argument(
        "--include-replies",
        action="store_true",
        help="Also fetch replies for each top-level comment (more quota)",
    )
    p.add_argument(
        "--progress-every",
        type=int,
        default=0,
        help="Print progress every N fetched comments per video (0 disables)",
    )
    p.add_argument(
        "--fast-balance",
        action="store_true",
        help="If set with --balanced, fetch only the balanced target size instead of fetching all then sampling",
    )
    p.add_argument(
        "--limit-per-video",
        type=int,
        default=None,
        help="Hard cap on comments fetched per video (helps quota)",
    )
    p.add_argument("--seed", type=int, default=42, help="Random seed for sampling")
    p.add_argument(
        "--no-filter",
        action="store_true",
        help="Disable spam/URL filtering",
    )
    p.add_argument(
        "--print-counts",
        action="store_true",
        help="Print per-video commentCount before fetching",
    )
    p.add_argument(
        "--csv-out",
        default="data/processed/gamst_comments.csv",
        help="CSV output path",
    )
    p.add_argument(
        "--sqlite-out",
        default="data/processed/gamst_comments.db",
        help="SQLite DB output path",
    )
    p.add_argument("--no-csv", action="store_true", help="Skip writing CSV")
    p.add_argument("--no-sqlite", action="store_true", help="Skip writing SQLite")
    return p.parse_args(argv)


def resolve_video_ids(videos_args: List[str]) -> List[str]:
    parts: List[str] = []
    for token in videos_args:
        # allow CSV inside a token
        for sub in token.replace("<", " ").replace(">", " ").split(","):
            parts.extend([t for t in sub.split() if t])
    ids: List[str] = []
    for p in parts:
        vid = parse_video_id(p)
        if vid:
            ids.append(vid)
        else:
            print(f"WARN: Could not parse video id from: {p}")
    # de-dup preserving order
    seen = set()
    uniq: List[str] = []
    for v in ids:
        if v not in seen:
            seen.add(v)
            uniq.append(v)
    return uniq


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)

    # Load env and API key
    load_env_if_possible()
    api_key = args.api_key or get_env_api_key() or ""
    if not api_key:
        print("ERROR: Missing YOUTUBE_API_KEY in env or --api-key.")
        return 2

    # Resolve video IDs
    video_ids = resolve_video_ids(args.videos)
    if len(video_ids) < 1:
        print("ERROR: Provide at least one video ID/URL via --videos.")
        return 2

    # Build service
    service = build_youtube_client(api_key)

    # Metadata and balanced target
    titles: List[str] = []
    counts: List[int] = []
    for vid in video_ids:
        title, count = get_video_metadata(service, vid)
        titles.append(title)
        counts.append(count)

    if args.print_counts:
        print(
            f"Counts: {video_ids[0]} -> {counts[0]} | {video_ids[1]} -> {counts[1]}"
        )

    # Compute per-video target
    per_video_target: List[Optional[int]] = [args.limit_per_video for _ in video_ids]
    if args.balanced:
        base = min(counts) if counts else None
        if base is not None and args.limit_per_video is not None:
            base = min(base, args.limit_per_video)
        per_video_target = [base for _ in video_ids]

    # Fetch
    all_comments: List[List[Comment]] = []
    for i, vid in enumerate(video_ids):
        title = titles[i]
        target = per_video_target[i]
        if args.balanced and not args.fast_balance:
            # fetch all for sampling later (may be heavy)
            fetched = fetch_comments(
                service,
                vid,
                title,
                max_items=None,
                order=args.order,
                include_replies=args.include_replies,
                progress_every=(args.progress_every or None),
                progress_cb=(
                    (lambda v, n, t=title: print(f"[progress] {t} ({v}) => {n}", flush=True))
                    if args.progress_every
                    else None
                ),
            )
        else:
            fetched = fetch_comments(
                service,
                vid,
                title,
                max_items=target,
                order=args.order,
                include_replies=args.include_replies,
                progress_every=(args.progress_every or None),
                progress_cb=(
                    (lambda v, n, t=title: print(f"[progress] {t} ({v}) => {n}", flush=True))
                    if args.progress_every
                    else None
                ),
            )
        all_comments.append(fetched)

    # Balanced sampling across N (if requested and we fetched all)
    if args.balanced and not args.fast_balance and all_comments:
        target = min(len(lst) for lst in all_comments)
        from .sampling import sample_list
        all_comments = [sample_list(lst, target, seed=args.seed) for lst in all_comments]

    # Spam filtering
    if not args.no_filter:
        all_comments = [filter_spam(lst) for lst in all_comments]

    merged: List[Comment] = [c for lst in all_comments for c in lst]

    # Outputs
    if not args.no_csv:
        save_csv(merged, args.csv_out)

    if not args.no_sqlite:
        init_db(args.sqlite_out)
        upsert_comments(args.sqlite_out, merged)

    # Summary
    summary = ", ".join([f"'{titles[i]}' => {len(all_comments[i])}" for i in range(len(video_ids))])
    print(f"Done. {summary}. Total: {len(merged)}.")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
