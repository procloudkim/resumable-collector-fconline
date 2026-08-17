from __future__ import annotations

"""
New-version wrapper for dailytrade HTML fetching utilities.

Use this module to stage new fetch logic (e.g., different waits,
headers, CAPTCHA strategies) without touching the current pipeline.
"""

from .fetcher import (
    BASE,
    polite_sleep,
    get_dailytrade_page,
    get_dailytrade_page_via_selenium,
    get_dailytrade_page_any,
)

__all__ = [
    "BASE",
    "polite_sleep",
    "get_dailytrade_page",
    "get_dailytrade_page_via_selenium",
    "get_dailytrade_page_any",
]

