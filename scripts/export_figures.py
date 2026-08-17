from __future__ import annotations

"""
고화질 한글 자료분석 이미지 일괄 생성 스크립트

목적(WHY)
- 로컬 Clean CSV(analytics/clean/*)를 사용해 발표용 그래프를 고해상도(PNG)로
  analytics/exports/ 경로에 저장한다. (seaborn 우선, 없으면 matplotlib 폴백)

산출물(WHAT)
- 메타 트렌드(연도별 TopN 출전)         → meta_topn_year.png
- 거래 가격(연도별 TopN 평균 가격)        → price_topn_year.png
- 빅매치 임팩트(±윈도우 출전 합계)        → event_impact.png
- 유튜브 감성 분포(막대)                 → sentiment_dist.png
- 감성–출전 상관(산점+회귀/상관계수)     → sentiment_play_corr.png
- 기술통계 요약                           → summary_stats.txt

사용(HOW)
  python scripts/export_figures.py --window 7 --event-index 0

주의
- 한글 폰트: Windows의 'Malgun Gothic' 우선. 없으면 가능한 시스템 폰트로 폴백.
- 입력 파일 부재 시 해당 그래프는 건너뛴다.
"""

import os
import json
from pathlib import Path
from typing import Optional, Tuple, List

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter

try:
    import seaborn as sns  # type: ignore
    _HAS_SNS = True
except Exception:
    _HAS_SNS = False

try:  # 선택 의존(없어도 작동)
    from scipy import stats as scistats  # type: ignore
except Exception:  # pragma: no cover
    scistats = None


ROOT = Path(__file__).resolve().parents[1]
ANALYTICS = ROOT / "analytics"
CLEAN = ANALYTICS / "clean"
EXPORTS = ANALYTICS / "exports"


def _ensure_dirs() -> None:
    EXPORTS.mkdir(parents=True, exist_ok=True)


def _setup_korean() -> None:
    plt.rcParams["axes.unicode_minus"] = False
    # Windows 기본: Malgun Gothic
    candidates = [
        "Malgun Gothic",
        "AppleGothic",
        "NanumGothic",
        "NanumGothicCoding",
        "DejaVu Sans",
    ]
    for f in candidates:
        try:
            plt.rcParams["font.sans-serif"] = [f]
            # smoke test
            _ = plt.figure()
            plt.text(0.5, 0.5, "한글", ha="center", va="center")
            plt.close(_)
            break
        except Exception:
            continue
    if _HAS_SNS:
        try:
            sns.set_theme(style="whitegrid")
        except Exception:
            pass


def _find_file(*candidates: str) -> Optional[Path]:
    for n in candidates:
        p = ROOT / n
        if p.exists():
            return p
    return None


def _detect_date_col(df: pd.DataFrame) -> Optional[str]:
    # 우선순위: 정확 일치/부분 일치 → to_datetime 성공 수 최대
    for cand in ["날짜", "date", "DATE", "일자"]:
        if cand in df.columns:
            return cand
    # 부분 일치
    for c in df.columns:
        if any(tok in str(c) for tok in ["날", "date", "Date", "DATE"]):
            return c
    # 최대 파싱 성공 컬럼 선택
    best, best_cnt = None, -1
    for c in df.columns:
        try:
            cnt = int(pd.to_datetime(df[c], errors="coerce").notna().sum())
        except Exception:
            cnt = -1
        if cnt > best_cnt:
            best_cnt = cnt
            best = c
    return best


def _load_topdaily() -> Optional[pd.DataFrame]:
    p = _find_file("analytics/clean/top_daily_record.clean.ko.strip.csv",
                   "analytics/clean/top_daily_record.clean.ko.csv",
                   "analytics/clean/top_daily_record.clean.csv",
                   "analytics/game/top_daily_record.csv")
    if not p:
        return None
    try:
        df = pd.read_csv(p)
        return df
    except Exception:
        return None


def _load_bestprice() -> Optional[pd.DataFrame]:
    p = _find_file("analytics/clean/best_price_daily.clean.names.strip.csv",
                   "analytics/clean/best_price_daily.clean.names.csv",
                   "analytics/clean/best_price_daily.clean.ko.csv",
                   "analytics/clean/best_price_daily.clean.csv",
                   "analytics/game/best_price_daily.csv")
    if not p:
        return None
    try:
        df = pd.read_csv(p)
        return df
    except Exception:
        return None


def _load_comments() -> Optional[pd.DataFrame]:
    p = _find_file("analytics/clean/comments.clean.csv",
                   "analytics/youtube/comments.csv")
    if not p:
        return None
    try:
        df = pd.read_csv(p)
        return df
    except Exception:
        return None


def _load_events() -> Optional[pd.DataFrame]:
    p = _find_file("config/events.csv")
    if not p:
        return None
    try:
        return pd.read_csv(p)
    except Exception:
        return None


def _format_thousands(x, pos=None):
    try:
        return f"{int(x):,}"
    except Exception:
        return str(x)


def _annotate_bar_values(ax: plt.Axes, horizontal: bool = True, fmt: str = "{:,}") -> None:
    # 막대 끝에 값 라벨 표시
    for p in ax.patches:
        try:
            if horizontal:
                val = p.get_width()
                y = p.get_y() + p.get_height() / 2
                ax.text(val, y, fmt.format(int(val)), va="center", ha="left", fontsize=9)
            else:
                val = p.get_height()
                x = p.get_x() + p.get_width() / 2
                ax.text(x, val, fmt.format(int(val)), va="bottom", ha="center", fontsize=9)
        except Exception:
            continue


def _savefig_multi(name_base: str, dpi: int = 220) -> List[Path]:
    """두 가지 레이아웃(PNG/PDF 동시 저장).

    - landscape: 11x6.5, portrait: 7.5x10
    - 파일명: name_base_{landscape|portrait}.{png|pdf}
    """
    _ensure_dirs()
    out_paths: List[Path] = []
    # 현재 fig를 가져와 복제 저장
    fig = plt.gcf()
    # landscape
    fig.set_size_inches(11, 6.5)
    for ext in ("png", "pdf"):
        p = EXPORTS / f"{name_base}_landscape.{ext}"
        fig.savefig(p, dpi=dpi, bbox_inches="tight")
        out_paths.append(p)
    # portrait
    fig.set_size_inches(7.5, 10)
    for ext in ("png", "pdf"):
        p = EXPORTS / f"{name_base}_portrait.{ext}"
        fig.savefig(p, dpi=dpi, bbox_inches="tight")
        out_paths.append(p)
    plt.close(fig)
    return out_paths


def plot_meta_topn_year(df_t: pd.DataFrame, topn: int = 10) -> Optional[Path]:
    # 컬럼 탐지
    date_col = _detect_date_col(df_t) or "date"
    player_col = "선수명" if "선수명" in df_t.columns else ("player_name" if "player_name" in df_t.columns else None)
    value_col = "출전_기록" if "출전_기록" in df_t.columns else ("출전" if "출전" in df_t.columns else None)
    if not player_col or not value_col:
        return None
    d = df_t[[date_col, player_col, value_col]].dropna().copy()
    d["year"] = pd.to_datetime(d[date_col]).dt.year
    latest = int(d["year"].max())
    gy = d[d["year"] == latest].groupby(player_col, as_index=False)[value_col].sum()
    gy = gy.sort_values(value_col, ascending=False).head(topn)
    plt.figure(figsize=(11, 6.5))
    if _HAS_SNS:
        ax = sns.barplot(data=gy, y=player_col, x=value_col, palette="deep")
    else:
        ax = plt.gca()
        ax.barh(gy[player_col], gy[value_col], color="#1f77b4")
    plt.title(f"연도별 Top{topn} 출전(최근 연도 {latest})")
    plt.xlabel("출전_기록")
    plt.ylabel("선수")
    ax = plt.gca()
    ax.xaxis.set_major_formatter(FuncFormatter(_format_thousands))
    _annotate_bar_values(ax, horizontal=True)
    _savefig_multi("meta_topn_year")
    return EXPORTS / "meta_topn_year_landscape.png"


def plot_price_topn_year(df_b: pd.DataFrame, topn: int = 10) -> Optional[Path]:
    bp_date = _detect_date_col(df_b)
    price_col = "거래 가격" if "거래 가격" in df_b.columns else ("price_value" if "price_value" in df_b.columns else None)
    pname = "선수 이름" if "선수 이름" in df_b.columns else ("player_name" if "player_name" in df_b.columns else None)
    if not (bp_date and price_col and pname):
        return None
    b = df_b[[bp_date, pname, price_col]].dropna().copy()
    b["year"] = pd.to_datetime(b[bp_date]).dt.year
    latest = int(b["year"].max())
    by = b[b["year"] == latest].groupby(pname, as_index=False)[price_col].mean()
    gg = by.sort_values(price_col, ascending=False).head(topn)
    plt.figure(figsize=(11, 6.5))
    if _HAS_SNS:
        ax = sns.barplot(data=gg, y=pname, x=price_col, palette="muted")
    else:
        ax = plt.gca()
        ax.barh(gg[pname], gg[price_col], color="#ff7f0e")
    plt.title(f"거래 가격 연도별 Top{topn}(최근 연도 {latest})")
    plt.xlabel("평균 거래 가격(BP)")
    plt.ylabel("선수")
    ax = plt.gca()
    ax.xaxis.set_major_formatter(FuncFormatter(_format_thousands))
    _annotate_bar_values(ax, horizontal=True, fmt="{:,}")
    _savefig_multi("price_topn_year")
    return EXPORTS / "price_topn_year_landscape.png"


def _detect_event_columns(dfe: pd.DataFrame) -> Tuple[str, str]:
    # ID 후보: event_id > match > event > name > title > 첫 컬럼
    id_col = None
    for pref in ["event_id", "match", "event", "name", "title"]:
        if pref in dfe.columns:
            id_col = pref
            break
    if id_col is None:
        id_col = dfe.columns[0]
    # 날짜 후보: to_datetime 성공 수 최대 컬럼
    best_col = None
    best_cnt = -1
    for c in dfe.columns:
        try:
            cnt = int(pd.to_datetime(dfe[c], errors="coerce").notna().sum())
        except Exception:
            cnt = -1
        if cnt > best_cnt:
            best_cnt = cnt
            best_col = c
    date_col = best_col or id_col
    return id_col, date_col


def plot_event_impact(df_t: pd.DataFrame, df_e: pd.DataFrame, window: int = 7, event_index: int = 0) -> Optional[Path]:
    if df_e.empty:
        return None
    id_col, dt_col = _detect_event_columns(df_e)
    row = df_e.iloc[event_index % len(df_e)]
    e_date = pd.to_datetime(row[dt_col], errors="coerce")
    if pd.isna(e_date):
        return None
    # topdaily 집계
    date_col = _detect_date_col(df_t) or "date"
    value_col = "출전_기록" if "출전_기록" in df_t.columns else ("출전" if "출전" in df_t.columns else None)
    if not value_col:
        return None
    td = df_t.copy()
    td[date_col] = pd.to_datetime(td[date_col])
    m = (td[date_col].dt.date >= (e_date.date() - pd.Timedelta(days=window))) & \
        (td[date_col].dt.date <= (e_date.date() + pd.Timedelta(days=window)))
    d = td.loc[m, [date_col, value_col]].copy()
    d["day"] = d[date_col].dt.date
    g = d.groupby("day", as_index=False)[value_col].sum()
    # 플롯
    plt.figure(figsize=(11, 6.5))
    if _HAS_SNS:
        sns.lineplot(data=g, x="day", y=value_col, marker="o")
    else:
        plt.plot(g["day"], g[value_col], marker="o")
    plt.axvline(e_date, color="red", linestyle="--", label="경기일")
    plt.title(f"빅매치 임팩트(±{window}일) — {str(row[id_col])}")
    plt.xlabel("날짜")
    plt.ylabel("출전 합계")
    plt.legend()
    _savefig_multi("event_impact")
    return EXPORTS / "event_impact_landscape.png"


def plot_sentiment_distribution(df_c: pd.DataFrame) -> Optional[Path]:
    sent_col = "sentiment_label" if "sentiment_label" in df_c.columns else ("sentiment" if "sentiment" in df_c.columns else None)
    if not sent_col:
        return None
    grp = df_c.groupby(sent_col).size().reset_index(name="count").sort_values("count", ascending=False)
    plt.figure(figsize=(11, 6.5))
    if _HAS_SNS:
        sns.barplot(data=grp, x=sent_col, y="count", palette="pastel")
    else:
        plt.bar(grp[sent_col], grp["count"], color="#2ca02c")
    plt.title("유튜브 감성 분포")
    plt.xlabel("감성")
    plt.ylabel("개수")
    ax = plt.gca()
    ax.yaxis.set_major_formatter(FuncFormatter(_format_thousands))
    _savefig_multi("sentiment_dist")
    return EXPORTS / "sentiment_dist_landscape.png"


def plot_sentiment_play_corr(df_t: pd.DataFrame, df_c: pd.DataFrame) -> Optional[Path]:
    # 날짜 정규화 및 일별 집계
    date_t = "날짜" if "날짜" in df_t.columns else "date"
    value_t = "출전_기록" if "출전_기록" in df_t.columns else ("출전" if "출전" in df_t.columns else None)
    if not value_t:
        return None
    td = df_t.copy()
    td[date_t] = pd.to_datetime(td[date_t]).dt.date
    daily_play = td.groupby(date_t, as_index=False)[value_t].sum().rename(columns={value_t: "출전합계"})

    sent_col = "sentiment_label" if "sentiment_label" in df_c.columns else ("sentiment" if "sentiment" in df_c.columns else None)
    if not sent_col:
        return None
    cc = df_c.copy()
    if "published_at" in cc.columns:
        cc["date_only"] = pd.to_datetime(cc["published_at"], errors="coerce").dt.date
    else:
        cc["date_only"] = pd.to_datetime(cc.get("date", pd.NaT), errors="coerce").dt.date
    daily_sent = cc.groupby("date_only")[sent_col].value_counts(normalize=True).rename("ratio").reset_index()
    pos = daily_sent[daily_sent[sent_col].str.lower().isin(["pos", "positive", "긍정"])].rename(columns={"ratio": "긍정비율", "date_only": date_t})
    merged = pd.merge(daily_play, pos[[date_t, "긍정비율"]], on=date_t, how="inner")

    # 상관/회귀
    r = np.corrcoef(merged["긍정비율"], merged["출전합계"])[0, 1]
    p = None
    if scistats is not None:
        try:
            r, p = scistats.pearsonr(merged["긍정비율"], merged["출전합계"])
        except Exception:
            pass

    plt.figure(figsize=(11, 6.5))
    if _HAS_SNS:
        sns.regplot(data=merged, x="긍정비율", y="출전합계", scatter_kws={"s": 30, "alpha": 0.7}, line_kws={"color": "red"})
    else:
        plt.scatter(merged["긍정비율"], merged["출전합계"], s=20, alpha=0.7)
    plt.title("감성–출전 상관")
    plt.xlabel("긍정비율")
    plt.ylabel("출전합계")
    plt.annotate(f"corr={r:.3f}{'' if p is None else f', p={p:.3g}'}", xy=(0.02, 0.95), xycoords="axes fraction")
    _savefig_multi("sentiment_play_corr")
    return EXPORTS / "sentiment_play_corr_landscape.png"


def export_summary(df_t: Optional[pd.DataFrame], df_b: Optional[pd.DataFrame], df_c: Optional[pd.DataFrame]) -> Path:
    _ensure_dirs()
    lines = []
    if df_t is not None:
        date_col = "날짜" if "날짜" in df_t.columns else "date"
        value_col = "출전_기록" if "출전_기록" in df_t.columns else ("출전" if "출전" in df_t.columns else None)
        lines.append("[TopDaily]")
        lines.append(f"rows={len(df_t)}")
        if value_col:
            lines.append(f"출전_기록 평균={df_t[value_col].dropna().mean():.2f}")
    if df_b is not None:
        price_col = "거래 가격" if "거래 가격" in df_b.columns else ("price_value" if "price_value" in df_b.columns else None)
        lines.append("\n[BestPrice]")
        lines.append(f"rows={len(df_b)}")
        if price_col:
            lines.append(f"거래 가격 평균={df_b[price_col].dropna().mean():.2f}")
    if df_c is not None:
        sent_col = "sentiment_label" if "sentiment_label" in df_c.columns else ("sentiment" if "sentiment" in df_c.columns else None)
        lines.append("\n[YouTube]")
        lines.append(f"rows={len(df_c)}")
        if sent_col:
            vc = df_c[sent_col].value_counts(normalize=True)
            for k, v in vc.items():
                lines.append(f"{k}: {v*100:.1f}%")
    out = EXPORTS / "summary_stats.txt"
    out.write_text("\n".join(lines), encoding="utf-8")
    return out


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser(description="고화질 한글 그래프 일괄 생성")
    ap.add_argument("--window", type=int, default=7, help="빅매치 임팩트 윈도우(±일)")
    ap.add_argument("--event-index", type=int, default=0, help="events.csv에서 사용할 이벤트 인덱스")
    ap.add_argument("--event-list", type=str, default="", help="쉼표구분 인덱스 목록(예: 0,2,5). 지정 시 일괄 처리")
    args = ap.parse_args()

    _ensure_dirs()
    _setup_korean()

    df_t = _load_topdaily()
    df_b = _load_bestprice()
    df_c = _load_comments()
    df_e = _load_events()

    if df_t is not None:
        plot_meta_topn_year(df_t)
    if df_b is not None:
        plot_price_topn_year(df_b)
    if df_t is not None and df_e is not None:
        if args.event_list:
            indices = [int(x) for x in args.event_list.split(",") if str(x).strip().isdigit()]
            for idx in indices:
                plot_event_impact(df_t, df_e, window=args.window, event_index=idx)
        else:
            plot_event_impact(df_t, df_e, window=args.window, event_index=args.event_index)
    if df_c is not None:
        plot_sentiment_distribution(df_c)
    if df_t is not None and df_c is not None:
        plot_sentiment_play_corr(df_t, df_c)

    export_summary(df_t, df_b, df_c)
    print(f"[THEN] 이미지/요약 저장 경로: {EXPORTS}")
    # 간단 커버/섹션 카드 생성
    try:
        for title, fname in [("FC 온라인 통합 분석", "cover"), ("요약", "section_summary"), ("결론", "section_conclusion")]:
            plt.figure(figsize=(11, 6.5))
            plt.axis("off")
            plt.text(0.5, 0.6, title, ha="center", va="center", fontsize=32, weight="bold")
            plt.text(0.5, 0.4, "Analytics Exports", ha="center", va="center", fontsize=16, color="#555")
            _savefig_multi(fname)
    except Exception:
        pass
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
