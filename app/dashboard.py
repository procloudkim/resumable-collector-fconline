"""
dashboard.py — Streamlit 대시보드
- 탭1: Top10 출전 추이
- 탭2: 랭커 스탯(일자별 골 합계 샘플)
- 사이드: 이름 검색→이미지 보기
"""
import os
import sys
import sqlite3
import pandas as pd
from collections import Counter
API_KEY = os.getenv("NEXON_OPENAPI_API_KEY")
try:
    import streamlit as st
    API_KEY = st.secrets.get("NEXON_OPENAPI_API_KEY") or API_KEY
except Exception:
    import streamlit as st  # fallback import to allow st.* usage below
    pass
from pathlib import Path
# Ensure repo root is on sys.path (for Streamlit Cloud running from app/)
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from app.core.utils import PROC, IMAGES
from app.services.meta import search_player_by_name, get_player_name
from app.services.images import ensure_player_image

st.set_page_config(page_title="FC Online Analytics", layout="wide")
if not API_KEY:
    st.warning("API 키가 없습니다. .streamlit/secrets.toml 또는 환경변수 설정이 필요합니다.")
st.title("FC Online — 선수 분석 대시보드")
st.caption("Data based on NEXON Open API")

# 도움말 / 데이터 사전 (간단 요약)
with st.expander("도움말 / 데이터 사전", expanded=False):
    st.markdown(
        "- 목적: FC 데이터센터 요소명을 존중하고, 비전공자도 이해할 수 있도록 간단히 설명합니다."
    )
    st.markdown(
        "- 핵심 컬럼: date(날짜), player_name(선수), season_code(시즌), position(포지션), enhance(강화), price_value(가격, 원)."
    )
    st.markdown(
        "- 로고/이미지: player_image_path, nation/league/team_logo_path는 로컬 캐시 경로입니다. 미존재 시 기본 아이콘을 표시하세요."
    )
    st.caption(
        "자세한 설명: docs/DATA_DICTIONARY_BESTPRICE_KR.md, docs/DASHBOARD_BDD_GUIDE_KR.md"
    )

tab1, tab2, tab3 = st.tabs(["📈 Top10 출전 추이", "🏅 랭커 스탯", "🖼️ 선수 이미지"])

# 탭1 — Top10 출전 추이
with tab1:
    csv = Path(PROC/"top10_trend.csv")
    if not csv.exists():
        st.warning("전처리 결과가 없습니다. 먼저 수집/전처리를 수행하세요.")
    else:
        df = pd.read_csv(csv, parse_dates=["date"])
        # Rename SPID columns to player names for readability
        cols = [c for c in df.columns if c != "date"]
        name_counts = Counter()
        rename_map = {}
        raw_names = []
        for c in cols:
            try:
                nm = get_player_name(int(str(c).strip()))
            except (ValueError, TypeError):
                nm = str(c)
            raw_names.append(nm)
            name_counts[nm] += 1
        for c, nm in zip(cols, raw_names):
            # Disambiguate duplicate names by appending spid
            if name_counts[nm] > 1:
                rename_map[c] = f"{nm} ({c})"
            else:
                rename_map[c] = nm
        df = df.rename(columns=rename_map)
        df = df.set_index("date").sort_index()
        st.line_chart(df, height=300)
        st.caption(
            f"rows={len(df)} · 읽는 법: 날짜별 출전 상위 선수 수치 추이를 선으로 이어서 비교합니다."
        )

# 탭2 — 랭커 스탯
with tab2:
    DB = Path("data/data.db")
    if not DB.exists():
        st.warning("DB가 없습니다. 랭커 스탯 수집을 먼저 수행하세요.")
    else:
        conn=sqlite3.connect(DB)
        q = """
        SELECT date(substr(create_date,1,10)) AS d, SUM(goal) AS goals
        FROM ranker_stats
        GROUP BY d
        ORDER BY d
        """
        dfx = pd.read_sql_query(q, conn, parse_dates=["d"])
        conn.close()
        if dfx.empty:
            st.info("랭커 스탯 데이터가 아직 없습니다.")
        else:
            st.line_chart(dfx.set_index("d")["goals"], height=300)

# 탭3 — 선수 이미지
with tab3:
    query = st.text_input("선수 이름으로 검색", placeholder="예: 손흥민 / Son Heung-Min")
    spid = st.text_input("spid 직접 입력", value="")
    if query:
        spids = search_player_by_name(query, fuzzy=True, limit=50)
        if spids:
            labels = [f"{get_player_name(s)} ({s})" for s in spids]
            choice = st.selectbox("검색 결과", labels, index=0)
            spid = choice.split("(")[-1].rstrip(")")
        else:
            st.info("검색 결과 없음")

    if st.button("이미지 보기") and spid.strip().isdigit():
        p = ensure_player_image(int(spid))
        if p and Path(p).exists():
            st.image(str(p), caption=f"{get_player_name(int(spid))} (spid={spid})", width=160)
        else:
            st.warning("이미지 다운로드 실패(경로 후보를 조정하세요).")
    else:
        st.caption("이미지를 보려면 spid를 입력하거나 이름으로 검색 후 선택하세요.")
