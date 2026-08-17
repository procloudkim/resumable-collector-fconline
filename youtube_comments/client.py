from typing import Optional

try:
    # Optional: load .env if python-dotenv is installed
    from dotenv import load_dotenv  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    load_dotenv = None


def load_env_if_possible() -> None:
    """Load .env if python-dotenv is available."""
    if load_dotenv is not None:
        try:
            load_dotenv()
        except Exception:
            pass


def build_youtube_client(api_key: str):
    """Build a YouTube Data API v3 client using an API key.

    Returns a `googleapiclient.discovery.Resource` (lazy import).
    """
    from googleapiclient.discovery import build  # lazy import to ease testing

    if not api_key:
        raise ValueError("Missing YouTube API key.")
    service = build("youtube", "v3", developerKey=api_key)
    return service

