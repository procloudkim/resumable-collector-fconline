from __future__ import annotations

import pandas as pd
from pathlib import Path
from typing import Iterable, Optional


ENCODINGS: tuple[str, ...] = ("utf-8-sig", "utf-8", "cp949", "euc-kr")


def _clean_kor_price_suffix(name: str) -> str:
    """Remove trailing price-like tokens from Korean names.

    Examples:
      "엘링 홀란 5,360조" -> "엘링 홀란"
      "크리스티아누 호날두 3,480조" -> "크리스티아누 호날두"
    """
    import re
    s = str(name or "")
    # strip trailing tokens like ' 5,360조', ' 5900조', ' 457억', ' 1만'
    s = re.sub(r"\s*[0-9][0-9,\.]*\s*(조|억|만)?\s*$", "", s)
    return s.strip()


def read_csv_smart(path: Path, usecols: Optional[Iterable[str]] = None) -> pd.DataFrame:
    """Read CSV trying multiple encodings. Returns empty DataFrame if not found.

    - Tries common Korean encodings as fallback.
    - If `usecols` is provided and some columns are missing, it will read full then filter those that exist.
    """
    if not path.exists():
        return pd.DataFrame()
    last_err: Exception | None = None
    for enc in ENCODINGS:
        try:
            df = pd.read_csv(path, encoding=enc)
            break
        except Exception as e:  # noqa: BLE001
            last_err = e
            df = pd.DataFrame()
    if df.empty and last_err:
        # last resort: ignore errors
        try:
            df = pd.read_csv(path, encoding="utf-8", errors="ignore")
        except Exception:
            return pd.DataFrame()
    if usecols:
        cols = [c for c in usecols if c in df.columns]
        if cols:
            return df[cols].copy()
    return df


def col_or(df: pd.DataFrame, *candidates: str) -> Optional[str]:
    for c in candidates:
        if c in df.columns:
            return c
    # fallback: approximate match by lower and removing spaces
    lowers = {c.lower().replace(" ", ""): c for c in df.columns}
    for want in candidates:
        key = want.lower().replace(" ", "")
        if key in lowers:
            return lowers[key]
    return None


def normalize_bestprice(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    out = df.copy()
    # canonical columns
    c_date = col_or(out, "date", "날짜") or "date"
    out[c_date] = pd.to_datetime(out[c_date], errors="coerce").dt.date
    out.rename(columns={c_date: "date"}, inplace=True)
    # player name clean
    name_col = col_or(out, "player_name", "선수_이름", "선수이름")
    if name_col and "player_name_clean" not in out.columns:
        out["player_name_clean"] = out[name_col].astype(str).map(_clean_kor_price_suffix)
    # numeric fixes
    for c in ("ovr", "pay", "enhance", "price_value", "spid"):
        if c in out.columns:
            out[c] = pd.to_numeric(out[c], errors="coerce")
    return out


def normalize_topdaily(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    out = df.copy()
    c_date = col_or(out, "date", "날짜") or "date"
    out[c_date] = pd.to_datetime(out[c_date], errors="coerce").dt.date
    out.rename(columns={c_date: "date"}, inplace=True)
    # player_name_clean from explicit or parse from base-info
    pcol = col_or(out, "선수_이름", "player_name")
    if not pcol:
        base = col_or(out, "선수_기본정보", "player_base")
        if base:
            out["player_name_clean"] = (
                out[base].astype(str).str.split(",").str[0].str.replace('"', "", regex=False).str.strip()
            )
    else:
        out["player_name_clean"] = out[pcol].astype(str)
    return out
