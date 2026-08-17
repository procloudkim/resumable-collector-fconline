from __future__ import annotations

"""
New-version wrapper for the rankers CLI.

Edit here if rankers scraping needs to diverge for the new pipeline.
"""

from .cli import main  # re-export entrypoint

__all__ = ["main"]

if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

