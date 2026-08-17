"""
분석 유틸: 이벤트 전후 집계/변화율 계산 등 (Streamlit 비의존)

의도(WHY)
- Streamlit UI와 분리된 순수 연산 유틸을 제공하여 테스트 가능성을 높인다.

함수
- compute_pre_post_stats: 특정 이벤트 날짜를 기준으로 ±window 구간의 평균/증감/증감율 계산
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Optional, Tuple

import pandas as pd


@dataclass
class PrePostStats:
    pre_mean: float
    post_mean: float
    delta: float
    pct_change: Optional[float]
    n_pre: int
    n_post: int


def _to_date(x) -> date:
    if isinstance(x, date) and not isinstance(x, datetime):
        return x
    return pd.to_datetime(x).date()


def compute_pre_post_stats(
    df: pd.DataFrame,
    *,
    date_col: str,
    value_col: str,
    event_date: str | date,
    window: int = 7,
) -> PrePostStats:
    """
    이벤트 날짜(event_date)를 기준으로 [-window, +window] 구간에서 0일을 제외하고
    pre/post 평균과 증감/증감율을 계산한다.

    Args:
        df: 입력 데이터프레임
        date_col: 날짜 컬럼명(문자열/날짜 모두 허용)
        value_col: 값 컬럼명(수치)
        event_date: 기준 날짜(문자열 또는 date)
        window: 양쪽 일수
    Returns:
        PrePostStats
    """
    if df.empty:
        return PrePostStats(0.0, 0.0, 0.0, None, 0, 0)

    e = _to_date(event_date)
    s = e - timedelta(days=window)
    t = e + timedelta(days=window)
    d = df.copy()
    d[date_col] = pd.to_datetime(d[date_col]).dt.date
    d = d[(d[date_col] >= s) & (d[date_col] <= t) & (d[date_col] != e)]
    if d.empty:
        return PrePostStats(0.0, 0.0, 0.0, None, 0, 0)
    d["rel"] = d[date_col].apply(lambda x: (x - e).days)
    pre = d[d["rel"] < 0][value_col]
    post = d[d["rel"] > 0][value_col]
    n_pre, n_post = int(pre.notna().sum()), int(post.notna().sum())
    pre_mean = float(pre.mean()) if n_pre else 0.0
    post_mean = float(post.mean()) if n_post else 0.0
    delta = post_mean - pre_mean
    pct = (delta / pre_mean) if pre_mean else None
    return PrePostStats(pre_mean, post_mean, delta, pct, n_pre, n_post)


__all__ = [
    "compute_pre_post_stats",
    "PrePostStats",
]

# --- 확장: p-value 계산 유틸(Scipy가 있으면 사용, 없으면 None 반환) ---
try:  # 선택 의존
    from scipy import stats as _scistats  # type: ignore
except Exception:  # pragma: no cover - 선택적 의존
    _scistats = None


def compute_pre_post_pvalue(
    df: pd.DataFrame,
    *,
    date_col: str,
    value_col: str,
    event_date: str | date,
    window: int = 7,
    method: str = "auto",
) -> Optional[float]:
    """
    pre/post 분할 데이터의 p-value를 계산(가능 시). Scipy 미설치 시 None.
    - auto: 쌍체 조건이 충족되면 Wilcoxon, 아니면 Welch t-test
    """
    if _scistats is None:
        return None
    e = _to_date(event_date)
    s = e - timedelta(days=window)
    t = e + timedelta(days=window)
    d = df.copy()
    d[date_col] = pd.to_datetime(d[date_col]).dt.date
    d = d[(d[date_col] >= s) & (d[date_col] <= t) & (d[date_col] != e)]
    if d.empty:
        return None
    d["rel"] = d[date_col].apply(lambda x: (x - e).days)
    pre = d[d["rel"] < 0][value_col].dropna()
    post = d[d["rel"] > 0][value_col].dropna()
    if len(pre) == 0 or len(post) == 0:
        return None
    # auto 선택: 길이가 같고 날짜가 매칭 가능한 경우 Wilcoxon, 그렇지 않으면 Welch t-test
    pval: Optional[float] = None
    try:
        if method == "wilcoxon" or (method == "auto" and len(pre) == len(post)):
            stat, p = _scistats.wilcoxon(pre.iloc[: len(post)], post)  # type: ignore
            pval = float(p)
        else:
            stat, p = _scistats.ttest_ind(pre, post, equal_var=False)  # Welch's t-test
            pval = float(p)
    except Exception:
        pval = None
    return pval


def build_prepost_summary(
    df: pd.DataFrame,
    *,
    date_col: str,
    value_col: str,
    group_col: Optional[str],
    event_date: str | date,
    window: int = 7,
) -> pd.DataFrame:
    """
    그룹(예: 선수)별 pre/post 요약 테이블 생성.
    Columns: [group, pre_mean, post_mean, delta, pct_change, n_pre, n_post, p, sig]
    """
    rows = []
    if group_col and (group_col in df.columns):
        groups = df[group_col].dropna().unique().tolist()
    else:
        groups = [None]
    for g in groups:
        sub = df[df[group_col] == g] if g is not None else df
        stats = compute_pre_post_stats(sub, date_col=date_col, value_col=value_col, event_date=event_date, window=window)
        p = compute_pre_post_pvalue(sub, date_col=date_col, value_col=value_col, event_date=event_date, window=window)
        sig = ""
        if p is not None:
            sig = "***" if p < 1e-3 else "**" if p < 1e-2 else "*" if p < 5e-2 else ""
        rows.append({
            (group_col or "group"): g,
            "pre_mean": stats.pre_mean,
            "post_mean": stats.post_mean,
            "delta": stats.delta,
            "pct_change": stats.pct_change,
            "n_pre": stats.n_pre,
            "n_post": stats.n_post,
            "p": p,
            "sig": sig,
        })
    out = pd.DataFrame(rows)
    return out

