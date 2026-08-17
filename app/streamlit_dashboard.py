"""
통합 분석 Streamlit 대시보드(로컬 CSV 기반)

탭 구성
- Tab 1: 5개년 메타 트렌드(출전/거래 요약)
- Tab 2: 빅매치 임팩트(±7일 전후 비교)
- Tab 3: 유튜브 감성 요약
- Tab 4: 감성–게임 상관(간단 버전)

BDD 로그는 화면 상단의 상태 패널에 노출한다.
"""
from __future__ import annotations
# 패키지 경로 보정: Streamlit이 app/ 경로를 CWD로 잡는 환경에서도
import sys
from pathlib import Path
_ROOT = Path(__file__).resolve().parents[1]  # repo root
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
from datetime import date
from typing import Optional

import pandas as pd
import streamlit as st

from app.analysis_utils import compute_pre_post_stats, build_prepost_summary
from app.dashboard_loader import (
    load_bestprice,
    load_comments,
    load_events,
    load_topdaily,
    load_player_map,
)
from app.clean_names import normalize_player_name
import json


st.set_page_config(page_title="FC 온라인 통합 분석", layout="wide")


def bdd_log(given: str, when: str, then: str) -> None:
    # 상세 로그 토글이 꺼져 있으면 표시하지 않음
    try:
        if not show_logs:
            return
    except NameError:
        pass
    st.markdown(f"- [GIVEN] {given}\n- [WHEN] {when}\n- [THEN] {then}")


st.title("EA SPORTS FC 온라인 — 통합 분석 대시보드")
st.caption("로컬 CSV 기반. Gold→Clean 계층을 사용합니다.")

# 날짜 한국어 표기 토글 및 도우미
use_korean_date = st.sidebar.checkbox("날짜 한국어 표기", value=True)

_DOW_KR = ["월", "화", "수", "목", "금", "토", "일"]

def fmt_date_kr(x) -> str:
    try:
        d = pd.to_datetime(x, errors="coerce").date()
        if pd.isna(d):
            return str(x)
        return f"{d.year}년 {d.month}월 {d.day}일({ _DOW_KR[d.weekday()] })"
    except Exception:
        return str(x)

# 데이터 로딩
@st.cache_data(show_spinner=False)
def _load_all():
    c, pc = load_comments()
    t, pt = load_topdaily()
    b, pb = load_bestprice()
    e, pe = load_events()
    return c, pc, t, pt, b, pb, e, pe


df_c, p_c, df_t, p_t, df_b, p_b, df_e, p_e = _load_all()

with st.expander("데이터셋 상태(BDD)", expanded=True):
    given = f"comments={len(df_c)} from={p_c} | topdaily={len(df_t)} from={p_t} | best_price={len(df_b)} from={p_b} | events={len(df_e)} from={p_e}"
    bdd_log(given, "load pandas DataFrame", "ready for analysis")

tabs = st.tabs(["메타 트렌드", "빅매치 임팩트", "유튜브 감성", "상관 분석(옵션)"])


with tabs[0]:
    st.subheader("5개년 메타 트렌드(간단 요약)")
    if df_t.empty:
        st.warning("Top daily 데이터가 없습니다.")
    else:
        # 날짜/선수명/출전_기록 집계
        date_col = "날짜" if "날짜" in df_t.columns else "date"
        player_col = (
            "선수의이름" if "선수의이름" in df_t.columns else (
            "선수명" if "선수명" in df_t.columns else (
            "선수 이름" if "선수 이름" in df_t.columns else (
            "player_name" if "player_name" in df_t.columns else None)))
        )
        value_col = "출전_기록" if "출전_기록" in df_t.columns else ("출전" if "출전" in df_t.columns else None)
        if not player_col or not value_col:
            st.error("필수 컬럼(선수명/출전_기록)이 없습니다.")
        else:
            d = df_t[[date_col, player_col, value_col]].dropna()
            d["year"] = pd.to_datetime(d[date_col]).dt.year
            grp = d.groupby(["year", player_col], as_index=False)[value_col].sum()
            # 연도 범위 선택(슬라이더)
            years = sorted(grp["year"].unique().tolist())
            yr_min, yr_max = st.select_slider("연도 범위", options=years, value=(years[0], years[-1]), key="year_range_main")
            topn = st.slider("Top N", min_value=5, max_value=30, value=10, key="topn_main")
            gy = grp[(grp["year"] >= yr_min) & (grp["year"] <= yr_max)]
            # 애니메이션 바차트(Plotly 있으면), 없으면 정적 차트
            # 레이스 차트 모드 선택: 연도 or 주단위
            race_mode = "연도"
            try:
                if race_mode == "연도":
                    import plotly.express as px  # type: ignore
                    fig = px.bar(
                        gy,
                        x=value_col,
                        y=player_col,
                        color=player_col,
                        animation_frame="year",
                        orientation="h",
                        category_orders={"year": sorted(gy["year"].unique().tolist())},
                    )
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    # 주단위 레이스: 매주 상위 N을 동적으로 정렬
                    import plotly.graph_objects as go  # type: ignore
                    from plotly.colors import qualitative as qual  # type: ignore
                    dfw = d[(d["year"] >= yr_min) & (d["year"] <= yr_max)].copy()
                    dfw["date_norm"] = pd.to_datetime(dfw[date_col])
                    # 전체 기간을 7일 간격으로 연속 생성(빈 주 포함)
                    start = dfw["date_norm"].min().to_period("W-MON").start_time.normalize()
                    end = dfw["date_norm"].max().to_period("W-MON").start_time.normalize()
                    weeks_full = pd.date_range(start, end, freq="7D").date.tolist()
                    dfw["week_start"] = dfw["date_norm"].dt.to_period("W-MON").dt.start_time.dt.date
                    agg = dfw.groupby(["week_start", player_col], as_index=False)[value_col].sum()
                    # 색상 매핑(선수별 고정) — 팔레트 순환
                    palette = (getattr(qual, "Plotly", ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728"]))
                    color_map = {}
                    def get_color(name: str) -> str:
                        if name not in color_map:
                            color_map[name] = palette[len(color_map) % len(palette)]
                        return color_map[name]
                    weeks = weeks_full  # 연속 주 시퀀스 사용
                    frames = []
                    # helper to build bar for a week
                    def make_bar(week):
                        sub = agg[agg["week_start"] == week].sort_values(value_col, ascending=False).head(topn)
                        y = list(sub[player_col])
                        x = list(sub[value_col])
                        # 상단이 최대가 되도록 뒤집기
                        y_rev = y[::-1]
                        x_rev = x[::-1]
                        colors = [get_color(n) for n in y_rev]
                        return go.Bar(x=x_rev, y=y_rev, orientation="h", marker_color=colors)
                    if weeks:
                        # 초기 프레임이 비어있을 수 있으므로 첫 비어있지 않은 주를 찾는다.
                        init_bar = None
                        first_label = None
                        for w in weeks:
                            bar = make_bar(w)
                            if len(bar["x"]) > 0:
                                init_bar = bar
                                first_label = w
                                break
                        if init_bar is None:
                            init_bar = go.Bar(x=[], y=[], orientation="h")
                            first_label = weeks[0]
                        fig = go.Figure(init_bar)
                        for w in weeks:
                            label = fmt_date_kr(w) if use_korean_date else str(w)
                            fig.add_frame(go.Frame(data=[make_bar(w)], name=label))
                        fig.update_layout(
                            title=f"주단위 레이스 {yr_min}–{yr_max}",
                            xaxis_title=value_col,
                            yaxis_title=player_col,
                            updatemenus=[
                                {
                                    "type": "buttons",
                                    "showactive": False,
                                    "buttons": [
                                        {"label": "▶", "method": "animate", "args": [None, {"fromcurrent": True, "frame": {"duration": 400, "redraw": True}, "transition": {"duration": 0}}]},
                                        {"label": "⏸", "method": "animate", "args": [[None], {"mode": "immediate", "frame": {"duration": 0, "redraw": False}, "transition": {"duration": 0}}]},
                                    ],
                                }
                            ],
                            sliders=[
                                {
                                    "steps": [
                                        {
                                            "label": (fmt_date_kr(w) if use_korean_date else str(w)),
                                            "method": "animate",
                                            "args": [[(fmt_date_kr(w) if use_korean_date else str(w))], {"mode": "immediate", "frame": {"duration": 0, "redraw": True}, "transition": {"duration": 0}}],
                                        }
                                        for w in weeks
                                    ],
                                    "currentvalue": {"prefix": "주: "},
                                }
                            ],
                        )
                        st.plotly_chart(fig, use_container_width=True)
                    else:
                        st.info("선택한 기간에 주단위 데이터가 없습니다.")
            except Exception as e:
                st.bar_chart(gy.sort_values(["year", value_col]).set_index(player_col)[value_col])
            bdd_log(f"years={yr_min}-{yr_max}", f"groupby sum({value_col})", f"rows={len(gy)} mode={race_mode}")

        # 보조: 거래 데이터 연도별 평균 가격 TopN (있을 때만)
        with st.expander("거래 가격 연도별 TopN(참고)", expanded=False):
            if not df_b.empty:
                bp_date = "날짜" if "날짜" in df_b.columns else ("date" if "date" in df_b.columns else None)
                price_col = "거래 가격" if "거래 가격" in df_b.columns else ("price_value" if "price_value" in df_b.columns else None)
                pname = (
                    "선수의이름" if "선수의이름" in df_b.columns else (
                    "선수 이름" if "선수 이름" in df_b.columns else (
                    "player_name" if "player_name" in df_b.columns else None))
                )
                if bp_date and price_col and pname:
                    b = df_b[[bp_date, pname, price_col]].dropna()
                    b["year"] = pd.to_datetime(b[bp_date]).dt.year
                    by = b.groupby(["year", pname], as_index=False)[price_col].mean()
                    if "year" in by.columns:
                        yopt = sorted(by["year"].unique().tolist())
                        sel_y = st.select_slider("연도 선택(거래)", options=yopt, value=yopt[-1], key="year_select_trade")
                        gg = by[by["year"] == sel_y].sort_values(price_col, ascending=False).head(topn)
                        st.bar_chart(gg.set_index(pname)[price_col])
                        bdd_log(f"year={sel_y}", f"avg {price_col}", f"top{topn} rows={len(gg)}")

with tabs[1]:
    st.subheader("빅매치 임팩트 분석(±7일)")
    if df_t.empty or df_e.empty:
        st.warning("Top daily 또는 events 데이터가 없습니다.")
    else:
        date_col = "날짜" if "날짜" in df_t.columns else "date"
        value_col = "출전_기록" if "출전_기록" in df_t.columns else ("출전" if "출전" in df_t.columns else None)
        player_col = (
            "선수의이름" if "선수의이름" in df_t.columns else (
            "선수명" if "선수명" in df_t.columns else (
            "선수 이름" if "선수 이름" in df_t.columns else (
            "player_name" if "player_name" in df_t.columns else None)))
        )
        if not value_col:
            st.error("필수 컬럼(출전_기록/출전)이 없습니다.")
        else:
            # 이벤트 선택(유연한 컬럼 탐지)
            def _detect_event_columns(dfe: pd.DataFrame):
                # ID 우선순위: event_id > match > event > name > title > 첫번째 컬럼
                id_col = None
                for pref in ["event_id", "match", "event", "name", "title"]:
                    if pref in dfe.columns:
                        id_col = pref
                        break
                if id_col is None:
                    id_col = dfe.columns[0]
                # 날짜 컬럼: to_datetime 성공 건수 최대인 컬럼 자동 선택
                best_col = None
                best_cnt = -1
                best_parsed = None
                for c in dfe.columns:
                    try:
                        ser = pd.to_datetime(dfe[c], errors="coerce")
                        cnt = int(ser.notna().sum())
                        if cnt > best_cnt:
                            best_cnt = cnt
                            best_col = c
                            best_parsed = ser.dt.date
                    except Exception:
                        continue
                if best_col is not None:
                    dfe = dfe.copy()
                    dfe["_event_date_auto"] = best_parsed
                return dfe, id_col, (best_col or None)

            df_e2, id_col, dt_col = _detect_event_columns(df_e)
            sel = st.selectbox("이벤트 선택", options=df_e2[id_col].astype(str), index=0)
            row = df_e2[df_e2[id_col].astype(str) == str(sel)].iloc[0]
            e_date = row.get("_event_date_auto")
            if pd.isna(e_date):
                st.warning("이벤트 날짜를 파싱할 수 없습니다. events.csv의 날짜 컬럼을 확인하세요.")
                bdd_log(f"event={sel} date=NaT", "skip analysis", "need valid event_date")
                st.stop()
            win = st.slider("윈도우(±일)", min_value=3, max_value=14, value=7, step=1, key="event_window_days")
            td = df_t.copy()
            td[date_col] = pd.to_datetime(td[date_col]).dt.date
            mask = (td[date_col] >= pd.to_datetime(e_date).date() - pd.Timedelta(days=win)) & (
                td[date_col] <= pd.to_datetime(e_date).date() + pd.Timedelta(days=win)
            ) & (td[date_col] != pd.to_datetime(e_date).date())
            # 이벤트 윈도우 내 선수 목록으로 필터 옵션 동기화
            players_in_win = (
                sorted(td.loc[mask, player_col].dropna().unique().tolist()) if player_col else []
            )
            # (옵션) 이벤트 국가/팀 기반 추천 필터
            filter_mode = st.radio("선수 추천 방식", ["전체 선수", "이벤트 기준 추천"], horizontal=True, index=0,
                                  help="이벤트의 국가/팀명을 사용해 해당 국가 선수만 우선 제안")
            suggest = players_in_win
            if filter_mode == "이벤트 기준 추천" and players_in_win:
                # 이벤트 토큰 추출(대한민국 vs 포르투갈 등)
                ev_text = str(sel)
                tokens = []
                for sep in ["vs", "VS", "대", " vs ", " VS ", " 대 "]:
                    if sep in ev_text:
                        parts = [p.strip() for p in ev_text.split(sep) if p.strip()]
                        tokens = parts
                        break
                if not tokens:
                    tokens = [ev_text]
                # 이름→국가레이블 매핑 구축(베스트프라이스 기반)
                name2nation = {}
                try:
                    # 국가 코드를 한국어 라벨로 매핑
                    label_map = {}
                    try:
                        with open("config/logo_labels_ko.json", "r", encoding="utf-8") as f:
                            label_map = json.load(f)
                    except Exception:
                        label_map = {}
                    bp_name = (
                        "선수의이름" if "선수의이름" in df_b.columns else (
                        "선수 이름" if "선수 이름" in df_b.columns else (
                        "player_name" if "player_name" in df_b.columns else None))
                    )
                    bp_nation = "국가 코드" if "국가 코드" in df_b.columns else ("nation_code" if "nation_code" in df_b.columns else None)
                    if bp_name and bp_nation:
                        tmp = df_b[[bp_name, bp_nation]].dropna().copy()
                        tmp["name_norm"] = tmp[bp_name].apply(normalize_player_name)
                        # 가장 빈도가 큰 국가코드를 대표값으로 사용
                        freq = tmp.groupby(["name_norm", bp_nation]).size().reset_index(name="cnt").sort_values(["name_norm", "cnt"], ascending=[True, False])
                        rep = freq.drop_duplicates("name_norm")
                        for _, r in rep.iterrows():
                            code = str(r[bp_nation])
                            ko = label_map.get(code, code)
                            name2nation[str(r["name_norm"])]= ko
                except Exception:
                    name2nation = {}
                if name2nation:
                    suggest = []
                    for nm in players_in_win:
                        ko = name2nation.get(normalize_player_name(nm))
                        if ko and any(t in ko for t in tokens):
                            suggest.append(nm)
                    # 추천이 너무 적으면 원래 목록 유지
                    if len(suggest) < 3:
                        suggest = players_in_win

            # 이벤트별 선수 preset 로드 → 기본 선택에 반영
            preset_default = []
            try:
                with open("config/event_presets_ko.json", "r", encoding="utf-8") as f:
                    presets = json.load(f)
                preset_entry = presets.get(str(sel))
                if isinstance(preset_entry, dict):
                    base = []
                    base.extend(preset_entry.get("players", []))
                    base.extend(preset_entry.get("home", []))
                    base.extend(preset_entry.get("away", []))
                    preset_default = base
                elif isinstance(preset_entry, list):
                    preset_default = preset_entry
            except Exception:
                preset_default = []
            defaults = [nm for nm in preset_default if nm in suggest]
            if not defaults:
                defaults = (suggest[:5] if suggest else [])
            sel_players = st.multiselect(
                "선수 선택", options=suggest, default=defaults
            )
            mask2 = mask
            if player_col and sel_players:
                mask2 = mask2 & td[player_col].isin(sel_players)
            window_df = td.loc[mask2, [date_col, value_col] + ([player_col] if player_col else [])]
            # 상대일 축(빅매치 기점) 추가
            window_df = window_df.copy()
            e_dt = pd.to_datetime(e_date).date()
            window_df["rel_day"] = pd.to_datetime(window_df[date_col]).dt.date.map(lambda d: (d - e_dt).days)
            # 상대일 위젯 숨김: 날짜 축 고정
            axis_mode = "날짜"
            # Hue(색상 구분) 옵션
            hue_opts = ["없음"]
            if player_col:
                hue_opts.append("선수")
            if "포지션" in td.columns:
                hue_opts.append("포지션")
            hue_sel = st.selectbox("색상 구분(Hue)", options=hue_opts, index=0, help="여러 선을 색상으로 구분")

            if axis_mode.startswith("상대일"):
                if hue_sel == "없음":
                    st.line_chart(window_df.set_index("rel_day")[value_col])
                else:
                    hue_col = player_col if hue_sel == "선수" else "포지션"
                    piv = window_df.pivot_table(index="rel_day", columns=hue_col, values=value_col, aggfunc="sum").fillna(0)
                    st.line_chart(piv)
            else:
                if hue_sel == "없음":
                    if use_korean_date:
                        window_df = window_df.copy()
                        window_df["날짜_한글"] = window_df[date_col].apply(fmt_date_kr)
                        st.line_chart(window_df.set_index("날짜_한글")[value_col])
                    else:
                        st.line_chart(window_df.set_index(date_col)[value_col])
                else:
                    axis = "날짜_한글" if use_korean_date else date_col
                    dfp = window_df.copy()
                    if use_korean_date:
                        dfp[axis] = dfp[date_col].apply(fmt_date_kr)
                    hue_col = player_col if hue_sel == "선수" else "포지션"
                    piv = dfp.pivot_table(index=axis, columns=hue_col, values=value_col, aggfunc="sum").fillna(0)
                    st.line_chart(piv)
            stats = compute_pre_post_stats(window_df, date_col=date_col, value_col=value_col, event_date=e_date, window=win)
            st.write({
                "pre_mean": stats.pre_mean,
                "post_mean": stats.post_mean,
                "delta": stats.delta,
                "pct_change": stats.pct_change,
                "n_pre": stats.n_pre,
                "n_post": stats.n_post,
            })
            bdd_log(f"event={sel} date={e_date}", f"window=±{win} days", f"rows={len(window_df)} delta={stats.delta}")

            # 멀티 선수 전후 요약 테이블(출전)
            if player_col:
                sum_play = build_prepost_summary(
                    td,
                    date_col=date_col,
                    value_col=value_col,
                    group_col=player_col,
                    event_date=e_date,
                    window=win,
                )
                if not sum_play.empty:
                    sum_play = sum_play.rename(columns={player_col or "group": "선수"})
                    if "delta" in sum_play.columns:
                        view_df2 = sum_play.sort_values("delta", ascending=False).head(50)
                    else:
                        view_df2 = sum_play.head(50)
                    st.dataframe(view_df2)
                    csv = sum_play.to_csv(index=False).encode("utf-8")
                    st.download_button(
                        "전후 요약(출전) CSV 다운로드",
                        data=csv,
                        file_name="prepost_play_summary.csv",
                        mime="text/csv",
                    )
                else:
                    st.info("선택한 윈도우/선수에서 출전 데이터가 부족하여 요약을 생성하지 못했습니다.")

            # 매핑 점검(spid) — 구성 파일 + 베스트프라이스 기반 보조 매핑
            with st.expander("선수명↔spid 매핑 점검", expanded=False):
                pm, pm_path = load_player_map()
                if pm_path is None or pm.empty:
                    st.info("config/player_map.csv 를 찾지 못했거나 비어 있습니다.")
                else:
                    name_col_pm = "name"
                    # 윈도우 내 선수 대비 매핑 커버리지 확인(이름 완전 일치 기준)
                    win_names = pd.DataFrame({"선수": players_in_win})
                    merged = win_names.merge(pm, left_on="선수", right_on=name_col_pm, how="left")
                    cov = int(merged["spid"].notna().sum())
                    st.write({"총 선수": len(players_in_win), "매핑됨": cov, "미매핑": len(players_in_win) - cov, "map_path": str(pm_path)})
                    st.dataframe(merged[merged["spid"].isna()].head(50))
                    bdd_log(
                        f"mapping check names={len(players_in_win)}",
                        f"matched={cov}",
                        f"unmatched={len(players_in_win)-cov}",
                    )

                # 보조 매핑: 베스트프라이스에서 name→spid 추정(정규화 이름 기준)
                try:
                    bp_date = "날짜" if "날짜" in df_b.columns else ("date" if "date" in df_b.columns else None)
                    spid_col = "선수 고유 ID" if "선수 고유 ID" in df_b.columns else ("spid" if "spid" in df_b.columns else None)
                    pname_bp = (
                        "선수의이름" if "선수의이름" in df_b.columns else (
                        "선수 이름" if "선수 이름" in df_b.columns else (
                        "player_name" if "player_name" in df_b.columns else None))
                    )
                    if bp_date and spid_col and pname_bp:
                        bp = df_b[[bp_date, spid_col, pname_bp]].dropna().copy()
                        bp["name_norm"] = bp[pname_bp].apply(normalize_player_name)
                        # 가장 빈번한 spid를 이름별 대표로 사용
                        m = (
                            bp.groupby(["name_norm", spid_col]).size().reset_index(name="cnt").sort_values(["name_norm", "cnt"], ascending=[True, False])
                        )
                        rep = m.drop_duplicates("name_norm").rename(columns={spid_col: "spid_rep"})[["name_norm", "spid_rep"]]
                        # 윈도우 선수명 정규화 후 커버리지 확인
                        win_df = pd.DataFrame({"선수": players_in_win})
                        win_df["name_norm"] = win_df["선수"].apply(normalize_player_name)
                        merged2 = win_df.merge(rep, on="name_norm", how="left")
                        cov2 = int(merged2["spid_rep"].notna().sum())
                        st.write({"추정 매핑(베스트프라이스)": True, "추정_매핑됨": cov2, "추정_미매핑": len(merged2) - cov2})
                        st.dataframe(merged2[merged2["spid_rep"].isna()].head(50))
                except Exception:
                    pass

            # 보조: 거래 가격 임팩트(있는 경우)
            with st.expander("거래 가격 임팩트(옵션)", expanded=False):
                if not df_b.empty:
                    bp_date = "날짜" if "날짜" in df_b.columns else ("date" if "date" in df_b.columns else None)
                    price_col = "거래 가격" if "거래 가격" in df_b.columns else ("price_value" if "price_value" in df_b.columns else None)
                    pname = (
                        "선수의이름" if "선수의이름" in df_b.columns else (
                        "선수 이름" if "선수 이름" in df_b.columns else (
                        "player_name" if "player_name" in df_b.columns else None))
                    )
                    if bp_date and price_col and pname:
                        bb = df_b.copy()
                        bb[bp_date] = pd.to_datetime(bb[bp_date]).dt.date
                        if sel_players:
                            bb = bb[bb[pname].isin(sel_players)]
                        m2 = (bb[bp_date] >= pd.to_datetime(e_date).date() - pd.Timedelta(days=win)) & (
                            bb[bp_date] <= pd.to_datetime(e_date).date() + pd.Timedelta(days=win)
                        ) & (bb[bp_date] != pd.to_datetime(e_date).date())
                        win_price = bb.loc[m2, [bp_date, price_col]]
                        # 상대일 축으로 표기
                        win_price = win_price.copy()
                        win_price["rel_day"] = pd.to_datetime(win_price[bp_date]).dt.date.map(lambda d: (d - e_dt).days)
                        if axis_mode.startswith("상대일"):
                            if sel_players:
                                w2 = bb.loc[m2, [bp_date, price_col, pname]].copy()
                                w2["rel_day"] = pd.to_datetime(w2[bp_date]).dt.date.map(lambda d: (d - e_dt).days)
                                pivp = w2.pivot_table(index="rel_day", columns=pname, values=price_col, aggfunc="mean").fillna(0)
                                st.line_chart(pivp)
                            else:
                                st.line_chart(win_price.set_index("rel_day")[price_col])
                        else:
                            if use_korean_date and sel_players:
                                w2 = bb.loc[m2, [bp_date, price_col, pname]].copy()
                                w2["날짜_한글"] = w2[bp_date].apply(fmt_date_kr)
                                pivp = w2.pivot_table(index="날짜_한글", columns=pname, values=price_col, aggfunc="mean").fillna(0)
                                st.line_chart(pivp)
                            elif use_korean_date:
                                win_price = win_price.copy()
                                win_price["날짜_한글"] = win_price[bp_date].apply(fmt_date_kr)
                                st.line_chart(win_price.set_index("날짜_한글")[price_col])
                            else:
                                if sel_players:
                                    w2 = bb.loc[m2, [bp_date, price_col, pname]].copy()
                                    pivp = w2.pivot_table(index=bp_date, columns=pname, values=price_col, aggfunc="mean").fillna(0)
                                    st.line_chart(pivp)
                                else:
                                    st.line_chart(win_price.set_index(bp_date)[price_col])
                        pst = compute_pre_post_stats(win_price, date_col=bp_date, value_col=price_col, event_date=e_date, window=win)
                        st.write({
                            "pre_price": pst.pre_mean,
                            "post_price": pst.post_mean,
                            "delta": pst.delta,
                            "pct_change": pst.pct_change,
                            "n_pre": pst.n_pre,
                            "n_post": pst.n_post,
                        })
                        bdd_log("price impact", f"window=±{win}", f"rows={len(win_price)} delta={pst.delta}")
                        # 멀티 선수 전후 요약(가격)
                        if player_col and pname in df_b.columns:
                            bb2 = bb.copy()
                            summary_price = build_prepost_summary(
                                bb2,
                                date_col=bp_date,
                                value_col=price_col,
                                group_col=pname,
                                event_date=e_date,
                                window=win,
                            )
                            if not summary_price.empty:
                                summary_price = summary_price.rename(columns={pname: "선수"})
                                if "delta" in summary_price.columns:
                                    view_df = summary_price.sort_values("delta", ascending=False).head(50)
                                else:
                                    view_df = summary_price.head(50)
                                st.dataframe(view_df)
                                csvp = summary_price.to_csv(index=False).encode("utf-8")
                                st.download_button(
                                    "전후 요약(가격) CSV 다운로드",
                                    data=csvp,
                                    file_name="prepost_price_summary.csv",
                                    mime="text/csv",
                                )
                            else:
                                st.info("선택한 윈도우/선수에서 가격 데이터가 부족하여 요약을 생성하지 못했습니다.")

with tabs[2]:
    st.subheader("유튜브 감성 대시보드")
    if df_c.empty:
        st.warning("댓글 데이터가 없습니다.")
    else:
        # stage 필터 & 감성 분포
        c = df_c.copy()
        stage_col = "stage" if "stage" in c.columns else None
        sent_col = "sentiment_label" if "sentiment_label" in c.columns else ("sentiment" if "sentiment" in c.columns else None)
        if not sent_col:
            st.error("sentiment_label 컬럼이 없습니다.")
        else:
            stages = sorted(c[stage_col].dropna().unique().tolist()) if stage_col else []
            stage_sel = st.multiselect("스테이지 필터", options=stages, default=stages)
            if stage_col and stage_sel:
                c = c[c[stage_col].isin(stage_sel)]
            grp = c.groupby(sent_col).size().reset_index(name="count").sort_values("count", ascending=False)
            st.bar_chart(grp.set_index(sent_col)["count"])
            bdd_log(f"comments={len(c)}", "groupby sentiment_label", f"classes={len(grp)}")

            # 키워드 기반 언급수 집계(선택)
            with st.expander("선수 키워드 언급 수(옵션)", expanded=False):
                text_col = "text" if "text" in c.columns else None
                if text_col:
                    # 키워드 사전 로딩
                    kw_file = st.text_input("키워드 사전 CSV 경로(config/player_keywords.csv)", value="config/player_keywords.csv")
                    keywords = {}
                    try:
                        if kw_file and Path(kw_file).exists():
                            kdf = pd.read_csv(kw_file)
                            # 예상 스키마: player, keywords(파이프 구분)
                            for _, row in kdf.iterrows():
                                player = str(row.get("player") or row.get("선수") or "").strip()
                                kw = str(row.get("keywords") or row.get("키워드") or "").split("|")
                                kw = [k.strip() for k in kw if k and str(k).strip()]
                                if player and kw:
                                    keywords[player] = kw
                    except Exception:
                        keywords = {}
                    # 간이 사전(사전 미존재 시 상위 플레이어명 사용)
                    if not keywords:
                        # Top daily에서 이름 얻기
                        cand_names = []
                        if not df_t.empty:
                            pcol = (
                                "선수의이름" if "선수의이름" in df_t.columns else (
                                "선수명" if "선수명" in df_t.columns else (
                                "선수 이름" if "선수 이름" in df_t.columns else (
                                "player_name" if "player_name" in df_t.columns else None)))
                            )
                            if pcol:
                                cand_names = pd.Series(df_t[pcol]).dropna().value_counts().head(20).index.tolist()
                        for nm in cand_names:
                            keywords[nm] = [nm]

                    if not keywords:
                        st.info("키워드 사전이 없습니다.")
                    else:
                        # 언급수 집계 (단순 포함, 대소문자 무시)
                        def count_mentions(s: str, kws: list[str]) -> int:
                            s2 = str(s or "").lower()
                            return int(any(k.lower() in s2 for k in kws))

                        rows = []
                        for player, kws in keywords.items():
                            cnt = int(c[text_col].apply(lambda x: count_mentions(x, kws)).sum())
                            rows.append({"선수": player, "언급수": cnt})
                        md = pd.DataFrame(rows).sort_values("언급수", ascending=False)
                        st.dataframe(md.head(50))

                        # 워드클라우드(옵션)
                        try:
                            from wordcloud import WordCloud  # type: ignore
                            import matplotlib.pyplot as plt
                            # 가장 언급수 높은 선수의 텍스트 모으기
                            top_player = md.iloc[0]["선수"] if not md.empty else None
                            if top_player:
                                kws = keywords[top_player]
                                mask = c[text_col].apply(lambda x: any(k.lower() in str(x).lower() for k in kws))
                                texts = "\n".join(c.loc[mask, text_col].astype(str).tolist())
                                # 폰트(Windows: Malgun Gothic)
                                font_path = "C:/Windows/Fonts/malgun.ttf"
                                wc = WordCloud(width=800, height=400, background_color="white", font_path=font_path)
                                wci = wc.generate(texts)
                                fig, ax = plt.subplots(figsize=(8, 4))
                                ax.imshow(wci, interpolation="bilinear")
                                ax.axis("off")
                                st.pyplot(fig)
                        except Exception:
                            st.info("워드클라우드 라이브러리가 없어 텍스트 표만 제공합니다.")

with tabs[3]:
    st.subheader("감성–게임 지표 상관(간단)")
    if df_t.empty or df_c.empty:
        st.info("상관 분석을 위해 topdaily와 comments 데이터가 필요합니다.")
    else:
        # 날짜 기준 간단 집계: 일별 긍정 비율 vs 출전 합계
        date_t = "날짜" if "날짜" in df_t.columns else "date"
        value_t = "출전_기록" if "출전_기록" in df_t.columns else ("출전" if "출전" in df_t.columns else None)
        sent_col = "sentiment_label" if "sentiment_label" in df_c.columns else ("sentiment" if "sentiment" in df_c.columns else None)
        if value_t and sent_col:
            td = df_t.copy()
            td[date_t] = pd.to_datetime(td[date_t]).dt.date
            daily_play = td.groupby(date_t, as_index=False)[value_t].sum().rename(columns={value_t: "출전합계"})
            cc = df_c.copy()
            cc["date_only"] = pd.to_datetime(cc["published_at"], errors="coerce").dt.date if "published_at" in cc.columns else pd.to_datetime(cc.get("date", pd.NaT), errors="coerce").dt.date
            daily_sent = cc.groupby("date_only")[sent_col].value_counts(normalize=True).rename("ratio").reset_index()
            pos = daily_sent[daily_sent[sent_col].str.lower().isin(["pos", "positive", "긍정"])].rename(columns={"ratio": "긍정비율", "date_only": date_t})
            merged = pd.merge(daily_play, pos[[date_t, "긍정비율"]], on=date_t, how="inner")
            st.dataframe(merged.head(50))
            st.scatter_chart(merged, x="긍정비율", y="출전합계")
            corr = merged[["긍정비율", "출전합계"]].corr().iloc[0, 1]
            st.write({"corr": float(corr) if pd.notna(corr) else None, "rows": len(merged)})
            bdd_log("joined daily sentiment vs play", "scatter corr", f"corr={corr}")

        # 다중 이벤트 비교 + 윈도우 감도(3/7/14)
        with st.expander("다중 이벤트 비교/윈도우 감도(옵션)", expanded=False):
            if df_e.empty:
                st.info("events 데이터가 필요합니다.")
            else:
                ecols = df_e.columns
                id_col = "event_id" if "event_id" in ecols else ecols[0]
                dt_col = "event_date" if "event_date" in ecols else ecols[1]
                df_e[dt_col] = pd.to_datetime(df_e[dt_col], errors="coerce").dt.date
                sel_ids = st.multiselect("이벤트 선택(복수)", options=df_e[id_col].astype(str).tolist(), default=df_e[id_col].astype(str).tolist()[:3])
                wins = [3, 7, 14]
                rows = []
                if sel_ids:
                    date_t = "날짜" if "날짜" in df_t.columns else "date"
                    value_t = "출전_기록" if "출전_기록" in df_t.columns else ("출전" if "출전" in df_t.columns else None)
                    if value_t:
                        td = df_t.copy()
                        td[date_t] = pd.to_datetime(td[date_t]).dt.date
                        for eid in sel_ids:
                            erow = df_e[df_e[id_col].astype(str) == str(eid)].iloc[0]
                            e_date = erow[dt_col]
                            for w in wins:
                                stt = compute_pre_post_stats(td[[date_t, value_t]], date_col=date_t, value_col=value_t, event_date=e_date, window=w)
                                rows.append({"event": eid, "window": w, "pre": stt.pre_mean, "post": stt.post_mean, "delta": stt.delta})
                        table = pd.DataFrame(rows)
                        st.dataframe(table)
                        bdd_log(f"events={len(sel_ids)}", f"windows={wins}", f"rows={len(table)}")
