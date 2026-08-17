from __future__ import annotations

import os
import pandas as pd
import numpy as np
import altair as alt
import streamlit as st


DATA_PATH = st.secrets.get("ANNOTATED_CSV", "data/processed/comments_with_sentiment.csv")


@st.cache_data(show_spinner=False)
def load_data(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    if "published_at" in df.columns:
        df["published_at"] = pd.to_datetime(df["published_at"], utc=True, errors="coerce")
    return df


def agg_timeseries(df: pd.DataFrame, bin_minutes: int, rolling: int) -> pd.DataFrame:
    d = df.dropna(subset=["published_at"]).copy()
    d["time_bin"] = d["published_at"].dt.floor(f"{bin_minutes}min")
    g = d.groupby("time_bin")
    agg = pd.DataFrame(
        {
            "pos": g.apply(lambda x: (x["sentiment_label"] == "positive").sum()),
            "neg": g.apply(lambda x: (x["sentiment_label"] == "negative").sum()),
            "neu": g.apply(lambda x: (x["sentiment_label"] == "neutral").sum()),
        }
    ).reset_index().sort_values("time_bin")
    total = (agg["pos"] + agg["neg"] + agg["neu"]).replace(0, np.nan)
    agg["pos_ratio"] = agg["pos"] / total
    for col in ("pos_ratio", "pos", "neg"):
        agg[f"{col}_smooth"] = agg[col].rolling(rolling, min_periods=1).mean()
    return agg


def wc_event_layer() -> alt.Chart:
    events = pd.DataFrame(
        {
            "date": pd.to_datetime(["2022-11-28", "2022-12-02", "2022-12-05"], utc=True),
            "label": ["가나전 패배", "포르투갈전 승리", "브라질전 패배"],
            "color": ["#d62728", "#2ca02c", "#d62728"],
        }
    )
    rule = (
        alt.Chart(events)
        .mark_rule(strokeDash=[6, 4])
        .encode(x="date:T", color=alt.Color("color:N", scale=None, legend=None))
    )
    text = (
        alt.Chart(events)
        .mark_text(align="left", dx=3, dy=-45)
        .encode(x="date:T", text="label:N", color=alt.Color("color:N", scale=None, legend=None))
    )
    return rule + text


def main():
    st.set_page_config(page_title="월드컵 댓글 감성 대시보드", layout="wide")
    st.title("월드컵 댓글 감성 대시보드")
    st.caption("집중 기간 감성 추이, 선수별 비교, 좋아요 가중 분석")

    df = load_data(DATA_PATH)
    if df.empty:
        st.error("주석된 CSV를 찾을 수 없습니다. sentiments annotate를 먼저 실행하세요.")
        return

    min_dt = pd.to_datetime(df["published_at"].min())
    max_dt = pd.to_datetime(df["published_at"].max())

    with st.sidebar:
        st.header("필터")
        start, end = st.date_input(
            "기간",
            value=(pd.Timestamp("2022-11-25"), pd.Timestamp("2022-12-09")),
            min_value=min_dt.date(),
            max_value=max_dt.date(),
        )
        bin_minutes = st.slider("시간 간격(분)", 5, 120, 15, step=5)
        rolling = st.slider("이동평균 창 크기", 1, 9, 3, step=1)
        add_events = st.checkbox("월드컵 이벤트 표시", value=True)

        # Players
        player_cols = [c for c in df.columns if c.startswith("mention_")]
        players = [c.replace("mention_", "") for c in player_cols]
        default_players = [p for p in ["손흥민", "황희찬", "김영권", "호날두"] if f"mention_{p}" in player_cols]
        picked = st.multiselect("선수 선택", options=players, default=default_players)

    # Filter by date (ensure timezone-aware bounds in UTC)
    def _to_utc(ts) -> pd.Timestamp:
        t = pd.to_datetime(ts)
        # Localize naive timestamps to UTC; otherwise convert to UTC
        try:
            return t.tz_localize("UTC") if t.tzinfo is None else t.tz_convert("UTC")
        except AttributeError:
            # pandas < 2.0 may not expose tzinfo; fallback via tz_localize errors
            try:
                return t.tz_localize("UTC")
            except Exception:
                return t.tz_convert("UTC")

    start_utc = _to_utc(start)
    end_utc = _to_utc(end) + pd.Timedelta(days=1)
    mask = (df["published_at"] >= start_utc) & (df["published_at"] < end_utc)
    df_range = df.loc[mask]

    # Overall trend
    agg = agg_timeseries(df_range, bin_minutes, rolling)
    base = alt.Chart(agg).encode(x=alt.X("time_bin:T", title="시간"))

    pos_ratio_chart = base.mark_line(color="#2ca02c").encode(y=alt.Y("pos_ratio_smooth:Q", title="긍정 비율"))
    counts_chart = (
        base.mark_line(color="#2ca02c").encode(y=alt.Y("pos_smooth:Q", title="댓글 수"))
        + base.mark_line(color="#d62728").encode(y="neg_smooth:Q")
    )
    if add_events:
        pos_ratio_chart = pos_ratio_chart + wc_event_layer()
        counts_chart = counts_chart + wc_event_layer()

    st.subheader("시간대별 긍정 비율")
    st.altair_chart(pos_ratio_chart.properties(width=1000, height=320), use_container_width=True)

    st.subheader("시간대별 감정 댓글 수")
    st.altair_chart(counts_chart.properties(width=1000, height=320), use_container_width=True)

    # Player overlays
    if picked:
        st.subheader("선수별 시간대 감성 추이")
        layers = []
        palette = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd", "#8c564b"]
        for i, pname in enumerate(picked):
            sub = df_range.loc[df_range[f"mention_{pname}"] == 1].copy()
            if sub.empty:
                continue
            agg_p = agg_timeseries(sub, bin_minutes, rolling)
            layers.append(
                alt.Chart(agg_p)
                .mark_line(color=palette[i % len(palette)])
                .encode(x="time_bin:T", y="pos_ratio_smooth:Q", tooltip=["time_bin:T", "pos:Q", "neg:Q", "pos_ratio:Q"])
                .properties(title=pname)
            )
        if layers:
            st.altair_chart(alt.layer(*layers).resolve_scale(y="independent").properties(width=1000, height=320), use_container_width=True)

    # Likes-weighted comparison (pre vs post)
    st.subheader("선수별 전/후 비교 (긍정 비율 · 좋아요 가중 점수)")
    if picked:
        recs = []
        for pname in picked:
            col = f"mention_{pname}"
            if col not in df.columns:
                continue
            g = df.loc[df[col] == 1]
            grp = g.groupby("stage")
            pos_ratio = grp.apply(lambda x: (x["sentiment_label"] == "positive").mean())
            def _w(x):
                w = pd.to_numeric(x.get("like_count", 0), errors="coerce").fillna(0).astype(float)
                s = pd.to_numeric(x.get("sentiment_score", 0.5), errors="coerce").astype(float)
                return float((s * (w + 1)).sum() / (w + 1).sum()) if len(x) else np.nan
            wscore = grp.apply(_w)
            recs.append({
                "player": pname,
                "pos_ratio_pre": float(pos_ratio.get("pre", np.nan)),
                "pos_ratio_post": float(pos_ratio.get("post", np.nan)),
                "wscore_pre": float(wscore.get("pre", np.nan)),
                "wscore_post": float(wscore.get("post", np.nan)),
            })
        comp = pd.DataFrame(recs)
        st.dataframe(comp)


if __name__ == "__main__":
    main()
