# -*- coding: utf-8 -*-
"""
test_parser_selectors.py: parser 및 selectors 모듈의 동작을 검증하는 테스트.
check_html-1.html과 check_html-2.html의 내용을 활용하여 파싱이 정확한지 확인합니다.
"""

from project2.app import parser

# 샘플 HTML 데이터 (check_html-2.html 일부 발췌: 상위 2개 선수 기록 행 포함)
sample_html = """<div class="tbody" id="divPalyerStatDetail">
    <div class="tr">
        <div class="td p_name">
            <div class="info_top"><div class="name">루시우</div></div>
            <div class="info_bottom">
                <span class="season"><img src="CC.png" alt=""></span>
                <span class="ability en_level8">8</span>
                <span class="position df"><span class="txt">CB</span><span class="skillData_1">126</span> </span>
                <span class="pay">26</span>
            </div>
        </div>
        <div class="td p_at">1,067</div>
        <div class="td p_atp">0.0<br>(46)</div>
        <div class="td p_g">0.0<br>(34)</div>
        <div class="td p_as">0.0<br>(12)</div>
        <div class="td p_pg">0.1<br>(91)</div>
        <div class="td p_ng">0.1<br>(77)</div>
        <div class="td p_p">93.3%<br>5,071/5,436</div>
        <div class="td p_d">91.5%<br>2,622/2,867</div>
        <div class="td p_s">11.9%<br>204/1,718</div>
        <div class="td p_df">1.3<br>(1,375)</div>
        <div class="td p_tt">58.9%<br>1,163/1,974</div>
        <div class="td p_td">12.8%<br>233/1,820</div>
        <div class="td p_tk">0.0<br>(35)</div>
        <div class="td p_av">6.1</div>
    </div>
    <div class="tr">
        <div class="td p_name">
            <div class="info_top"><div class="name">로타어 마테우스</div></div>
            <div class="info_bottom">
                <span class="season"><img src="CC.png" alt=""></span>
                <span class="ability en_level8">8</span>
                <span class="position mf"><span class="txt">CM</span><span class="skillData_2">128</span> </span>
                <span class="pay">28</span>
            </div>
        </div>
        <div class="td p_at">1,022</div>
        <div class="td p_atp">0.5<br>(543)</div>
        <div class="td p_g">0.3<br>(263)</div>
        <div class="td p_as">0.3<br>(280)</div>
        <div class="td p_pg">0.6<br>(620)</div>
        <div class="td p_ng">0.2<br>(200)</div>
        <div class="td p_p">92.7%<br>14,328/15,457</div>
        <div class="td p_d">93.0%<br>10,391/11,179</div>
        <div class="td p_s">6.8%<br>37/544</div>
        <div class="td p_df">0.7<br>(757)</div>
        <div class="td p_tt">50.7%<br>720/1,419</div>
        <div class="td p_td">4.2%<br>49/1,153</div>
        <div class="td p_tk">0.0<br>(15)</div>
        <div class="td p_av">7.2</div>
    </div>
</div>"""


def test_parse_daily_record():
    """parser.parse_page가 샘플 HTML에서 정확한 데이터를 추출하는지 테스트"""
    from datetime import datetime

    test_date = datetime(2020, 5, 20).date()
    result = parser.parse_page(test_date, sample_html)
    # 두 개의 선수 기록이 파싱되었는지 확인
    assert isinstance(result, list)
    assert len(result) == 2

    # 첫 번째 선수 정보 검증
    first = result[0]
    # 랭킹 컬럼 (1부터 시작)
    assert first["rank"] == 1
    # 날짜 컬럼 (형식 확인)
    assert first["date"] == "2020-05-20"
    # 선수 이름 및 기본정보 결합 확인
    assert first["선수 기본정보"] == "루시우, 8, CB 126, 26"
    # 출전 수는 int로 변환되어야 함
    assert isinstance(first["출전"], int)
    assert first["출전"] == 1067
    # 공격 포인트 등 다른 칼럼은 문자열로 그대로 있는지 (예: "0.0 (46)")
    assert first["공격 포인트"] == "0.0 (46)"
    assert first["득점"] == "0.0 (34)"
    assert first["평점"] == "6.1"

    # 두 번째 선수 정보 검증 (일부 필드만 확인)
    second = result[1]
    assert second["rank"] == 2
    assert "로타어 마테우스" in second["선수 기본정보"]
    assert second["출전"] == 1022
    assert second["도움"] == "0.3 (280)"

