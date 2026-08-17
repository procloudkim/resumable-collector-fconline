from __future__ import annotations

import random
import time
from dataclasses import dataclass
from typing import Callable, Dict, Iterable, List, Optional, Tuple


@dataclass
class Comment:
    video_id: str
    video_title: str
    comment_id: str
    author: Optional[str]
    text: str
    like_count: int
    published_at: Optional[str]
    updated_at: Optional[str]
    is_reply: bool = False
    parent_id: Optional[str] = None


def get_video_metadata(service, video_id: str) -> Tuple[str, int]:
    """Return (title, comment_count) for a video.

    Raises KeyError/ValueError if not found.
    """
    req = service.videos().list(part="snippet,statistics", id=video_id)
    resp = req.execute()
    items = resp.get("items", [])
    if not items:
        raise ValueError(f"Video not found: {video_id}")
    item = items[0]
    title = item.get("snippet", {}).get("title", "")
    count_str = item.get("statistics", {}).get("commentCount", "0")
    try:
        count = int(count_str)
    except Exception:
        count = 0
    return title, count


def _fetch_replies(
    service,
    parent_id: str,
    video_id: str,
    video_title: str,
    text_format: str = "plainText",
    max_items: Optional[int] = None,
    already: int = 0,
    progress_every: Optional[int] = None,
    progress_cb: Optional[Callable[[str, int], None]] = None,
    total_counter: Optional[List[int]] = None,
) -> List[Comment]:
    """Fetch all replies for a top-level comment (parent_id)."""
    results: List[Comment] = []
    page_token: Optional[str] = None
    def _execute_with_retry(req):
        # Basic exponential backoff for transient errors / rate limiting
        for attempt in range(6):
            try:
                return req.execute()
            except Exception as e:  # HttpError from googleapiclient
                # try to detect status code if present
                status = getattr(getattr(e, "resp", None), "status", None)
                if status in (403, 429, 500, 503):
                    if attempt >= 5:
                        raise
                    delay = (1.5 ** attempt) + random.random()
                    time.sleep(delay)
                    continue
                raise

    while True:
        req = service.comments().list(
            part="snippet",
            parentId=parent_id,
            textFormat=text_format,
            maxResults=100,
            pageToken=page_token,
        )
        resp = _execute_with_retry(req)
        items = resp.get("items", [])
        for it in items:
            snip = it.get("snippet", {})
            results.append(
                Comment(
                    video_id=video_id,
                    video_title=video_title,
                    comment_id=it.get("id", ""),
                    author=snip.get("authorDisplayName"),
                    text=snip.get("textDisplay", ""),
                    like_count=int(snip.get("likeCount", 0) or 0),
                    published_at=snip.get("publishedAt"),
                    updated_at=snip.get("updatedAt"),
                    is_reply=True,
                    parent_id=parent_id,
                )
            )
            if total_counter is not None:
                total_counter[0] += 1
                if progress_every and progress_cb and (total_counter[0] % progress_every == 0):
                    progress_cb(video_id, total_counter[0])
            if max_items is not None and (already + len(results)) >= max_items:
                return results
        page_token = resp.get("nextPageToken")
        if not page_token:
            break
    return results


def fetch_comments(
    service,
    video_id: str,
    video_title: str,
    max_items: Optional[int] = None,
    order: str = "time",
    text_format: str = "plainText",
    include_replies: bool = False,
    progress_every: Optional[int] = None,
    progress_cb: Optional[Callable[[str, int], None]] = None,
) -> List[Comment]:
    """Fetch top-level comments for a video.

    - Uses commentThreads.list with maxResults=100 paging.
    - If max_items is provided, stops after fetching at least that many.
    - Returns a list of Comment objects.
    """
    results: List[Comment] = []
    page_token: Optional[str] = None

    def _execute_with_retry(req):
        for attempt in range(6):
            try:
                return req.execute()
            except Exception as e:
                status = getattr(getattr(e, "resp", None), "status", None)
                if status in (403, 429, 500, 503):
                    if attempt >= 5:
                        raise
                    delay = (1.5 ** attempt) + random.random()
                    time.sleep(delay)
                    continue
                raise

    total_counter = [0]  # mutable holder for total count including replies
    while True:
        req = service.commentThreads().list(
            part="snippet",
            videoId=video_id,
            textFormat=text_format,
            maxResults=100,
            order=order,
            pageToken=page_token,
        )
        resp = _execute_with_retry(req)
        items = resp.get("items", [])
        for it in items:
            top = it.get("snippet", {}).get("topLevelComment", {})
            top_snip = top.get("snippet", {})
            comment_id = top.get("id") or it.get("id") or ""
            results.append(
                Comment(
                    video_id=video_id,
                    video_title=video_title,
                    comment_id=comment_id,
                    author=top_snip.get("authorDisplayName"),
                    text=top_snip.get("textDisplay", ""),
                    like_count=int(top_snip.get("likeCount", 0) or 0),
                    published_at=top_snip.get("publishedAt"),
                    updated_at=top_snip.get("updatedAt"),
                    is_reply=False,
                    parent_id=None,
                )
            )
            total_counter[0] += 1
            if progress_every and progress_cb and (total_counter[0] % progress_every == 0):
                progress_cb(video_id, total_counter[0])
            if max_items is not None and len(results) >= max_items and not include_replies:
                return results

            if include_replies:
                total_reply_count = it.get("snippet", {}).get("totalReplyCount", 0) or 0
                if total_reply_count:
                    replies = _fetch_replies(
                        service,
                        parent_id=comment_id,
                        video_id=video_id,
                        video_title=video_title,
                        text_format=text_format,
                        max_items=max_items,
                        already=len(results),
                        progress_every=progress_every,
                        progress_cb=progress_cb,
                        total_counter=total_counter,
                    )
                    results.extend(replies)
                    if max_items is not None and len(results) >= max_items:
                        return results

        page_token = resp.get("nextPageToken")
        if not page_token:
            break

    return results
