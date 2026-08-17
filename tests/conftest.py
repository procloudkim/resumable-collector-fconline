"""
Ensure project root is importable during tests.

Some environments run pytest with a working directory that does not include
the repository root on sys.path, causing `import app.core` to fail during
collection. This small shim inserts the repo root at the front of sys.path.
"""
from __future__ import annotations
import sys
from pathlib import Path


def _ensure_repo_root_on_path() -> None:
    # tests/ -> repo root is one parent up
    root = Path(__file__).resolve().parents[1]
    root_str = str(root)
    if root_str not in sys.path:
        sys.path.insert(0, root_str)


_ensure_repo_root_on_path()

# Debug: show that conftest ran and where root is; won't harm tests output.
try:
    # Keep it minimal to avoid noisy output under -q; only on verbose runs.
    import os
    if os.environ.get("PYTEST_DEBUG_IMPORTS") == "1":
        from pathlib import Path as _P
        _root = _P(__file__).resolve().parents[1]
        print(f"[conftest] root={_root}")
        print(f"[conftest] on path? {str(_root) in sys.path}")
        print(f"[conftest] app exists? {(_root / 'app').exists()}")
        print(f"[conftest] app/core exists? {(_root / 'app' / 'core').exists()}")
        try:
            import importlib
            importlib.import_module('app')
            print("[conftest] import app: OK")
        except Exception as _e:
            print(f"[conftest] import app: FAIL -> {_e}")
except Exception:
    pass
