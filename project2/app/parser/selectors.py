# -*- coding: utf-8 -*-
"""
parser.selectors 모듈: HTML 구조에 대한 CSS Selector를 모아 관리합니다.
HTML 태그나 클래스 이름이 변경될 경우 이 파일만 수정하여 파싱 로직에 반영할 수 있도록 합니다.
"""

# 크롤링 대상 HTML 내 특정 요소들을 찾기 위한 CSS 선택자 상수들을 정의합니다.

# 일별 기록 페이지에서 '출전' 카테고리 선택 관련 (사용 여부에 따라 클릭 용도로 사용)
CATEGORY_BUTTON = "a.selector_target"  # 현재 선택된 카테고리 표시 버튼 (예: '출전')
CATEGORY_ITEM_MATCHCOUNT = "a[data-no='MATCHCOUNT']"  # 드롭다운 리스트 중 '출전' 항목

# 선수 기록 표(table) 관련 선택자
# 선수별 기록 행(Row) - 과거/현재 DOM 차이를 모두 포괄하도록 유니온 셀렉터 사용
# - divPalyerStatDetail (오탈자 존재하는 구버전)
# - divPlayerStatDetail (신규/정정 버전 가능성 고려)
# - .tbody .tr (백업 범용 셀렉터)
PLAYERS_ROWS = "#divPalyerStatDetail .tr, #divPlayerStatDetail .tr, .tbody .tr"
PLAYER_NAME = ".name"            # 선수 이름
PLAYER_LEVEL = ".ability"        # 선수 강화 레벨 (능력치 강화를 숫자로 표기)
PLAYER_POSITION_TEXT = ".position .txt"  # 선수 포지션 약어 (예: FW, MF, DF, GK 등)
PLAYER_POSITION_STAT = ".position span[class^='skillData']"  # 선수 포지션 관련 능력치 (OVR 등 숫자)
PLAYER_PAY = ".pay"              # 선수 급여

# 통계 컬럼별 선택자 (각 .td에 해당 클래스가 붙음)
STAT_APPEARANCE = ".p_at"        # 출전 (경기 수)
STAT_ATTACK_POINT = ".p_atp"     # 공격 포인트
STAT_GOAL = ".p_g"               # 득점
STAT_ASSIST = ".p_as"            # 도움
STAT_EFF_SHOOT = ".p_pg"         # 유효 슈팅
STAT_NORMAL_SHOOT = ".p_ng"      # 일반 슈팅
STAT_PASS_SUCCESS = ".p_p"       # 패스 성공률
STAT_DRIBBLE_SUCCESS = ".p_d"    # 드리블 성공률
STAT_AERIAL_SUCCESS = ".p_s"     # 공중볼 경합 성공률
STAT_INTERCEPT = ".p_df"         # 가로채기
STAT_TACKLE_SUCCESS = ".p_tt"    # 태클 성공률
STAT_BLOCK_SUCCESS = ".p_td"     # 차단 성공률
STAT_SAVE = ".p_tk"              # 선방(골 차단)
STAT_RATING = ".p_av"            # 평점
