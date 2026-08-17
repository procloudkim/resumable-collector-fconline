from __future__ import annotations

import math
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

import pandas as pd
import streamlit as st

try:
    import plotly.express as px  # type: ignore
    HAVE_PLOTLY = True
except Exception:  # pragma: no cover
    HAVE_PLOTLY = False

from scripts.csv_loader import read_csv_smart, normalize_bestprice, normalize_topdaily


ROOT = Path(__file__).resolve().parent
BEST_CSV = ROOT / "analytics" / "new_analytics" / "best_price_daily.clean.names.strip.fixed.csv"
TOP_CSV = ROOT / "analytics" / "new_analytics" / "top_daily_record.clean.ko.strip.fixed.csv"
EVENTS_CSV = ROOT / "config" / "events.csv"


def fmt_price(v: Optional[float]) -> str:
    try:
        iv = int(v) if v is not None else None
    except Exception:
        return str(v)
    return "-" if iv is None else f"{iv:,}"


@st.cache_data(show_spinner=False)
def load_best() -> pd.DataFrame:
    df = read_csv_smart(BEST_CSV)
    return normalize_bestprice(df)


@st.cache_data(show_spinner=False)
def load_top() -> pd.DataFrame:
    df = read_csv_smart(TOP_CSV)
    return normalize_topdaily(df)


@st.cache_data(show_spinner=False)
def load_events() -> pd.DataFrame:
    if not EVENTS_CSV.exists():
        return pd.DataFrame()
    df = pd.read_csv(EVENTS_CSV, encoding="utf-8-sig")
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.date
    return df


def welch_t_and_p(pre: pd.Series, post: pd.Series) -> tuple[float, float]:
    a = pd.to_numeric(pre, errors="coerce").dropna()
    b = pd.to_numeric(post, errors="coerce").dropna()
    n1, n2 = len(a), len(b)
    if n1 == 0 or n2 == 0:
        return 0.0, 1.0
    m1, m2 = float(a.mean()), float(b.mean())
    s1, s2 = float(a.std(ddof=1)) if n1 > 1 else 0.0, float(b.std(ddof=1)) if n2 > 1 else 0.0
    denom = math.sqrt((s1 * s1) / max(n1, 1) + (s2 * s2) / max(n2, 1))
    if denom == 0:
        return 0.0, 1.0
    t = (m2 - m1) / denom
    p = math.erfc(abs(t) / math.sqrt(2.0))
    return t, p


def render_tab_best():
    st.title("Best Price (신규 데이터셋)")
    best = load_best()
    if best.empty:
        st.error(f"가격 데이터가 없습니다: {BEST_CSV}")
        return
    dmin, dmax = best["date"].min(), best["date"].max()
    with st.sidebar:
        st.header("필터")
        r = st.date_input("기간", value=(dmin, dmax), min_value=dmin, max_value=dmax)
        if isinstance(r, tuple):
            d_from, d_to = r
        else:
            d_from, d_to = dmin, dmax
        seasons = st.multiselect("시즌", sorted(best.get("season_code", pd.Series(dtype=str)).dropna().unique().tolist()))
        positions = st.multiselect("포지션", sorted(best.get("position", pd.Series(dtype=str)).dropna().unique().tolist()))
        enhance = st.slider("강화(+n)", 1, 10, (1, 10), key="best_enhance_range")
        qtext = st.text_input("선수 검색", "")
        topn = st.slider("표시 Top N", 10, 200, 50, step=10, key="best_topn")
    df = best[(best["date"] >= d_from) & (best["date"] <= d_to)].copy()
    if seasons:
        df = df[df["season_code"].isin(seasons)]
    if positions:
        df = df[df["position"].isin(positions)]
    lo, hi = enhance
    if "enhance" in df.columns:
        df = df[(pd.to_numeric(df["enhance"], errors="coerce") >= lo) & (pd.to_numeric(df["enhance"], errors="coerce") <= hi)]
    if qtext:
        df = df[df.get("player_name_clean", df.get("player_name", pd.Series(index=df.index, dtype=str))).fillna("").str.contains(qtext, case=False)]

    k1, k2, k3, k4 = st.columns(4)
    with k1:
        st.metric("카드 수", f"{len(df):,}")
    with k2:
        st.metric("고유 선수 수", f"{df['spid'].nunique() if 'spid' in df.columns else df['player_name_clean'].nunique():,}")
    with k3:
        st.metric("최대 가격", fmt_price(pd.to_numeric(df.get("price_value", pd.Series()), errors="coerce").max()))
    with k4:
        st.metric("기간", f"{d_from} ~ {d_to}")

    st.subheader("Top N (가격 내림차순)")
    df["price_value"] = pd.to_numeric(df.get("price_value"), errors="coerce")
    disp_name = df.get("player_name_clean", df.get("player_name")).fillna("")
    top = df.assign(player=disp_name).sort_values(["price_value"], ascending=[False]).head(topn)
    st.dataframe(top[["player", "spid", "season_code", "position", "ovr", "enhance", "price_value", "date"]], width='stretch', hide_index=True)

    st.subheader("선수 가격 추이")
    options = top["player"].astype(str).tolist()
    sel = st.selectbox("선수", options=options)
    if sel:
        one = df[disp_name == sel].sort_values("date")
        if HAVE_PLOTLY:
            fig = px.line(one, x="date", y="price_value", markers=True)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.line_chart(one.set_index("date")["price_value"], height=320)


def render_tab_event():
    st.title("Big Match Impact (신규 데이터셋)")
    best = load_best()
    events = load_events()
    if best.empty:
        st.error("가격 데이터 없음")
        return
    if events.empty:
        st.info("config/events.csv를 준비해 주세요.")
        return
    labels = [f"{r.date} · {r.get('name','')}" for _, r in events.iterrows()]
    with st.sidebar:
        idx = st.selectbox("이벤트", options=list(range(len(events))), format_func=lambda i: labels[i], index=0)
        days = st.slider("전/후 일수(±)", 3, 21, 7, key="event_days_window")
        topn = st.slider("표시 Top N", 10, 200, 50, step=10, key="event_topn")
    ev = events.iloc[int(idx)]
    ev_date: date = ev["date"]
    start, end = ev_date - timedelta(days=days), ev_date + timedelta(days=days)
    st.session_state["event_range"] = (start, end)
    # 추가 옵션: 이상치 절단(%)과 로그 스케일
    with st.sidebar:
        winsor = st.slider("이상치 절단(%)", 0, 20, 0, key="winsor_event")
        logscale = st.checkbox("로그 스케일(시계열)", value=False, key="logscale_event")
    win = best[(best["date"] >= start) & (best["date"] <= end)].copy()
    if winsor and winsor > 0:
        q = winsor / 100.0
        lo = pd.to_numeric(win.get("price_value"), errors="coerce").quantile(q)
        hi = pd.to_numeric(win.get("price_value"), errors="coerce").quantile(1 - q)
        win["price_value"] = pd.to_numeric(win.get("price_value"), errors="coerce").clip(lower=lo, upper=hi)
    disp = win.get("player_name_clean", win.get("player_name")).fillna("")
    pre = win[win["date"] < ev_date]
    post = win[win["date"] > ev_date]
    pre_g = pre.groupby([disp])['price_value'].mean().reset_index(name='pre_mean').rename(columns={disp.name: 'player'})
    post_g = post.groupby([disp])['price_value'].mean().reset_index(name='post_mean').rename(columns={disp.name: 'player'})
    stats = pd.merge(pre_g, post_g, on='player', how='outer')
    rows = []
    for _, r in stats.iterrows():
        s_pre = pre.loc[disp[pre.index] == r['player'], 'price_value']
        s_post = post.loc[disp[post.index] == r['player'], 'price_value']
        t, p = welch_t_and_p(s_pre, s_post)
        delta = (r.get('post_mean') or float('nan')) - (r.get('pre_mean') or float('nan'))
        base = r.get('pre_mean', float('nan'))
        pct = (delta / base * 100.0) if pd.notna(delta) and pd.notna(base) and base != 0 else float('nan')
        rows.append({"player": r['player'], "pre_mean": r.get('pre_mean'), "post_mean": r.get('post_mean'), "delta": delta, "pct": pct, "t": t, "p": p})
    out = pd.DataFrame(rows)
    out['abs_pct'] = out['pct'].abs()
    out = out.sort_values(['abs_pct','delta'], ascending=[False, False]).head(topn)
    st.subheader("전/후 평균 가격 비교 (Top N)")
    st.dataframe(out[["player","pre_mean","post_mean","delta","pct","t","p"]]
                 .style.format({'pre_mean': fmt_price, 'post_mean': fmt_price, 'delta': fmt_price, 'pct': '{:.1f}%'.format, 't': '{:.2f}'.format, 'p': '{:.3f}'.format}),
                 width='stretch', hide_index=True)
    # 출전 Proxy: TopDailyRecord에서 ±윈도우 출전 횟수 요약
    top = load_top()
    if not top.empty and "player_name_clean" in top.columns:
        top["date"] = pd.to_datetime(top["date"], errors="coerce").dt.date
        top_win = top[(top["date"] >= start) & (top["date"] <= end)].copy()
        top_win["appear"] = 1
        pre_ap = top_win[top_win["date"] < ev_date].groupby("player_name_clean")["appear"].sum().rename("appear_pre")
        post_ap = top_win[top_win["date"] > ev_date].groupby("player_name_clean")["appear"].sum().rename("appear_post")
        ap = pd.concat([pre_ap, post_ap], axis=1).fillna(0)
        ap["appear_delta"] = ap["appear_post"] - ap["appear_pre"]
        ap_view = ap.loc[ap.index.isin(out["player"])].reset_index().rename(columns={"player_name_clean":"player"})
        st.subheader("출전 Proxy 요약")
        st.dataframe(ap_view[["player","appear_pre","appear_post","appear_delta"]], width='stretch', hide_index=True)

    # 선택 선수 시계열(로그 스케일 옵션 적용)
    if not out.empty:
        st.subheader("선택 선수 시계열")
        sel = st.selectbox("선수", options=out["player"].tolist(), key="event_player_sel")
        if sel:
            disp_all = win.get("player_name_clean", win.get("player_name")).fillna("")
            one = win[(disp_all == sel)].sort_values("date")
            if HAVE_PLOTLY and not one.empty:
                fig = px.line(one, x='date', y='price_value', markers=True, title=f"{sel} 가격 추이")
                if logscale:
                    fig.update_yaxes(type='log')
                fig.add_vline(x=pd.to_datetime(ev_date), line_dash='dash', line_color='red')
                st.plotly_chart(fig, use_container_width=True)


def render_tab_sentiment():
    st.title("YouTube 감성 대시보드")
    st.info("주석 댓글 CSV를 찾아 시계열을 표시합니다. 별도 파일이 없으면 생략됩니다.")
    # 유지: 기존 파이프라인과 호환. 여기서는 간단 표기만 유지.


def render_tab_corr():
    st.title("감성–게임 상관")
    st.info("가격 평균과 감성 비율의 상관계수를 계산합니다(데이터가 있을 때).")


def render_tab_meta():
    st.title("메타 트렌드")
    best = load_best()
    if best.empty:
        st.error("가격 데이터 없음")
        return
    df = best.copy()
    df["month"] = pd.to_datetime(df["date"]).to_period("M").dt.to_timestamp("M")
    st.subheader("월별 평균 가격")
    avgm = df.groupby("month")["price_value"].mean().reset_index(name="mean_price")
    if HAVE_PLOTLY:
        fig = px.line(avgm, x="month", y="mean_price", markers=True)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.line_chart(avgm.set_index("month")["mean_price"], height=320)


def _app() -> None:
    st.set_page_config(page_title="FC 온라인 분석 대시보드(신규셋)", layout="wide")
    tabs = st.tabs(["Tab 1 · Best Price", "Tab 2 · Big Match Impact", "Tab 3 · Sentiment", "Tab 4 · Correlation", "Tab 5 · Meta Trends"])
    with tabs[0]:
        render_tab_best()
    with tabs[1]:
        render_tab_event()
    with tabs[2]:
        render_tab_sentiment()
    with tabs[3]:
        render_tab_corr()
    with tabs[4]:
        render_tab_meta()


if __name__ == "__main__":
    _app()
