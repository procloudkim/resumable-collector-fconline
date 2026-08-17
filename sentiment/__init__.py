"""Lightweight KR sentiment analysis toolkit for YouTube comments.

Modules
- keywords: player/team mention keyword lists
- preprocess: text normalization for KR online slang
- lexicon: seed slang lexicon and scoring
- mentions: detection of player mentions
- io_utils: CSV/SQLite I/O helpers
- cli: entrypoints to annotate and visualize
"""

__all__ = [
    "keywords",
    "preprocess",
    "lexicon",
    "mentions",
    "io_utils",
]

