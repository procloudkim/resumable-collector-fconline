from __future__ import annotations

# Default video_id -> stage mapping (can be extended or overridden)

VIDEO_STAGE_MAP = {
    # 경기 한참 전
    "3pWbGukqJMk": "pre_early",
    # 경기 전
    "KdJ3SjfqH0A": "pre",
    "DK1b6SUfAYU": "pre",
    "495WxvVexSU": "pre",
    "6iNvWivKc1Q": "pre",
    "M5sHUvQiQ_Q": "pre",
    "XwAmMkLE2ms": "pre",
    # 경기 후
    "VwJo3WJO0hk": "post",
    "Zk8m94viAaM": "post",
    "877WV_ejUJc": "post",
    # 경기 후(호날두)
    "6-SlWtgTkgg": "ronaldo",
}

# Korean display labels for stages
STAGE_LABELS = {
    "pre_early": "경기 한참 전",
    "pre": "경기 전",
    "post": "경기 후",
    "ronaldo": "경기 후(호날두)",
}
