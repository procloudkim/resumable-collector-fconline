import os
import re
from typing import Optional


YOUTUBE_ID_RE = re.compile(r"^[a-zA-Z0-9_-]{11}$")


def parse_video_id(url_or_id: str) -> Optional[str]:
    """
    Parse a YouTube video ID from a URL or return the ID if already provided.

    Supports:
    - https://www.youtube.com/watch?v=VIDEO_ID
    - https://youtu.be/VIDEO_ID
    - Bare 11-char video ID
    """
    s = (url_or_id or "").strip()
    if not s:
        return None

    # Bare ID
    if YOUTUBE_ID_RE.match(s):
        return s

    # youtu.be short URL
    m = re.search(r"https?://(?:www\.)?youtu\.be/([a-zA-Z0-9_-]{11})", s)
    if m:
        return m.group(1)

    # youtube watch URL with v= param
    m = re.search(r"https?://(?:www\.)?youtube\.com/watch\?[^#]*v=([a-zA-Z0-9_-]{11})", s)
    if m:
        return m.group(1)

    # Embedded or share formats
    m = re.search(r"https?://(?:www\.)?youtube\.com/embed/([a-zA-Z0-9_-]{11})", s)
    if m:
        return m.group(1)

    # Shorts (not typical for this task, but safe to handle)
    m = re.search(r"https?://(?:www\.)?youtube\.com/shorts/([a-zA-Z0-9_-]{11})", s)
    if m:
        return m.group(1)

    return None


def get_env_api_key(env_key: str = "YOUTUBE_API_KEY") -> Optional[str]:
    """Fetch API key from environment; returns None if missing."""
    return os.getenv(env_key)

