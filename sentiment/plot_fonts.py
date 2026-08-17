from __future__ import annotations

import os
from typing import Optional


def ensure_korean_font(preferred: Optional[str] = None, search_dir: Optional[str] = None, verbose: bool = False) -> Optional[str]:
    """Ensure matplotlib can render Hangul by registering a TTF and setting rcParams.

    Order of selection:
    1) Environment variable `SENTIMENT_KR_FONT_PATH` (path to .ttf/.otf)
    2) `preferred` font file path if provided
    3) Fonts under `assets/fonts/*.ttf|*.otf` (repo local)
    4) Fall back to common families if present (Malgun Gothic, NanumGothic, AppleGothic)

    Returns the chosen font family name (or None if unchanged).
    """
    try:
        import matplotlib
        from matplotlib import font_manager
        from glob import glob
    except Exception:
        return None

    # 1) Env var
    env_path = os.environ.get("SENTIMENT_KR_FONT_PATH")
    candidates = []
    if env_path and os.path.isfile(env_path):
        candidates.append(env_path)

    # 2) Preferred explicit path
    if preferred and os.path.isfile(preferred):
        candidates.append(preferred)

    # 3) assets/fonts
    if search_dir is None:
        repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
        search_dir = os.path.join(repo_root, "assets", "fonts")
    for ext in ("ttf", "otf"):
        candidates.extend(sorted(glob(os.path.join(search_dir, f"*.{ext}"))))

    # Try to register and set from candidates
    def _set_font_from_file(path: str) -> Optional[str]:
        try:
            from matplotlib import font_manager
            fp = font_manager.FontProperties(fname=path)
            name = fp.get_name()
            font_manager.fontManager.addfont(path)
            matplotlib.rcParams["font.family"] = [name]
            matplotlib.rcParams["axes.unicode_minus"] = False
            return name
        except Exception:
            return None

    for path in candidates:
        fam = _set_font_from_file(path)
        if fam:
            if verbose:
                print(f"Using Korean font: {fam} ({path})")
            return fam

    # 4) Common system families
    for fam in ("Malgun Gothic", "NanumGothic", "AppleGothic"):
        try:
            matplotlib.rcParams["font.family"] = [fam]
            matplotlib.rcParams["axes.unicode_minus"] = False
            if verbose:
                print(f"Using system family: {fam}")
            return fam
        except Exception:
            continue

    return None

