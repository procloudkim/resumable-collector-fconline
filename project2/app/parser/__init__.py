# -*- coding: utf-8 -*-
"""
parser 패키지: Selenium으로 가져온 HTML 페이지 내용을 파싱하여 원하는 데이터 필드를 추출합니다.
WHY: HTML 구조가 복잡하므로 BeautifulSoup을 활용한 CSS 셀렉터로 필요한 데이터를 정확히 선택합니다.
HOW: HTML 문자열을 BeautifulSoup으로 파싱한 뒤, selectors에 정의된 CSS 선택자를 이용해 각 선수의 기록 행을 찾고,
     행 내 각 열(column)의 텍스트를 추출하여 Python 데이터 구조(list of dict)로 반환합니다.
"""

from bs4 import BeautifulSoup
from . import selectors  # parser 패키지 내부의 CSS 선택자 모듈


def parse_page(date, html):
    """
    주어진 날짜의 HTML 콘텐츠에서 '출전' 랭킹 데이터를 파싱하여 리스트로 반환합니다.
    각 요소는 한 선수의 기록을 나타내는 딕셔너리이며, date와 rank 및 모든 통계 컬럼을 포함합니다.

    WHY: 테스트 가능한 순수 함수로 구현하여 TDD와 유지보수성을 확보합니다.
    HOW: CSS 선택자로 각 셀을 안전하게 선택하고, 텍스트 정제와 타입 변환(출전 수 정수화)을 수행합니다.
    """
    # BeautifulSoup 객체 생성 (HTML 파싱) - html.parser를 사용 (내장 파서)
    soup = BeautifulSoup(html, 'html.parser')
    rows = soup.select(selectors.PLAYERS_ROWS)
    result = []
    rank = 1  # HTML에 랭킹 정보가 없으므로, 행 순서대로 1부터 부여합니다.
    for row in rows:
        try:
            # 선수 기본정보 칼럼 파싱
            name_tag = row.select_one(selectors.PLAYER_NAME)
            level_tag = row.select_one(selectors.PLAYER_LEVEL)
            pos_text_tag = row.select_one(selectors.PLAYER_POSITION_TEXT)
            pos_stat_tag = row.select_one(selectors.PLAYER_POSITION_STAT)
            pay_tag = row.select_one(selectors.PLAYER_PAY)

            # 각 요소의 텍스트 추출 및 불필요한 공백 제거
            name = name_tag.get_text(strip=True) if name_tag else ""
            # 이름이 비어 있으면 유효한 선수 행이 아니라고 판단하고 스킵
            if not name:
                continue
            level = level_tag.get_text(strip=True) if level_tag else ""
            pos_text = pos_text_tag.get_text(strip=True) if pos_text_tag else ""
            pos_stat = pos_stat_tag.get_text(strip=True) if pos_stat_tag else ""
            pay = pay_tag.get_text(strip=True) if pay_tag else ""

            # 선수 기본정보를 하나의 문자열로 합칩니다.
            # WHY: '선수 기본정보' 칼럼이 이름/강화/포지션/능력치/급여를 포함하므로 단일 필드로 보존합니다.
            # HOW: 존재하는 요소만 순서대로 연결하여 불필요한 구두점/공백을 방지합니다.
            # 예: "루시우, 8, CB 126, 26"
            player_info = f"{name}"
            if level:
                player_info += f", {level}"
            if pos_text or pos_stat:
                if pos_text and pos_stat:
                    player_info += f", {pos_text} {pos_stat}"
                elif pos_text:
                    player_info += f", {pos_text}"
                elif pos_stat:
                    player_info += f", {pos_stat}"
            if pay:
                player_info += f", {pay}"

            # 통계 수치 칼럼들 파싱
            # HTML 상에서 <br> 태그가 있는 경우, get_text(separator=" ")로 한 줄로 결합합니다.
            def get_stat_text(selector):
                cell = row.select_one(selector)
                if not cell:
                    return ""
                return cell.get_text(separator=" ", strip=True)

            # 출전 수 (정수형, 천 단위 콤마 제거)
            appearance_text = get_stat_text(selectors.STAT_APPEARANCE)
            match_count = int(appearance_text.replace(",", "")) if appearance_text else 0

            # 나머지 통계 칼럼들은 문자열 그대로 저장 (UI 표기 형태 유지)
            attack_point = get_stat_text(selectors.STAT_ATTACK_POINT)
            goal = get_stat_text(selectors.STAT_GOAL)
            assist = get_stat_text(selectors.STAT_ASSIST)
            eff_shoot = get_stat_text(selectors.STAT_EFF_SHOOT)
            normal_shoot = get_stat_text(selectors.STAT_NORMAL_SHOOT)
            pass_success = get_stat_text(selectors.STAT_PASS_SUCCESS)
            dribble_success = get_stat_text(selectors.STAT_DRIBBLE_SUCCESS)
            aerial_success = get_stat_text(selectors.STAT_AERIAL_SUCCESS)
            intercept = get_stat_text(selectors.STAT_INTERCEPT)
            tackle_success = get_stat_text(selectors.STAT_TACKLE_SUCCESS)
            block_success = get_stat_text(selectors.STAT_BLOCK_SUCCESS)
            save = get_stat_text(selectors.STAT_SAVE)
            rating = get_stat_text(selectors.STAT_RATING)

            record = {
                "date": date.strftime("%Y-%m-%d"),  # date는 datetime.date 객체라고 가정, 문자열로 저장
                "rank": rank,
                "선수 기본정보": player_info,
                "출전": match_count,
                "공격 포인트": attack_point,
                "득점": goal,
                "도움": assist,
                "유효 슈팅": eff_shoot,
                "일반 슈팅": normal_shoot,
                "패스 성공률": pass_success,
                "드리블 성공률": dribble_success,
                "공중볼 경합 성공률": aerial_success,
                "가로채기": intercept,
                "태클 성공률": tackle_success,
                "차단 성공률": block_success,
                "선방(골 차단)": save,
                "평점": rating,
            }
            result.append(record)
            rank += 1
        except Exception:
            # 개별 행 처리 중 오류 발생 시: 해당 선수 데이터를 건너뛰고 다음 행으로 진행
            # WHY: 특정 행 파싱 중 문제가 생겨도 전체 크롤링을 중단하지 않도록 함.
            continue

    return result
