from __future__ import annotations

"""
New-version wrapper for the daily trade crawler CLI.

Initially delegates to the existing implementation to preserve behavior.
Edit this file to diverge safely for the new pipeline.
"""

from .cli import main  # re-export entrypoint

__all__ = ["main"]

if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

