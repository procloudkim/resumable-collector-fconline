from __future__ import annotations

"""
카드형 bestPrice DOM 선택자 정의

WHY: 연도별로 소소한 차이가 있어도 핵심 구조는 동일하다. 선택자를 한 곳에서 관리해 유지보수성을 높인다.
HOW: CSS 선택자 상수와 보조 정규식을 모듈화한다.
"""

# 카드 루트(최우선)
CARDS = "#bestPrice #divBestTradeArea_price .item_list, #divBestTradeArea_price .item_list, #divBestTradeArea_price .swiper-slide"

# SPID(우선: outlink href 쿼리 spid)
SPID_LINK = "a.outlink[href*='PlayerInfo?spid=']"

# 이름
NAME = ".playerCardInfoBottom .nameWrap .name span, .player_wrap[title]"
NAME_HIDDEN = "a.outlink > span.hidden"

# 시즌
SEASON_IMG = ".playerCardInfoBottom .nameWrap .season img[src]"

# 포지션/OVR/급여/강화
POSITION = ".playerCardInfoSide .position"
OVR = ".playerCardInfoSide .ovr.value"
PAY = ".playerCardInfoSide .pay span"
ENHANCE = ".buildUp a"

# 가격
PRICE = ".price_wrap .price"

# 이미지
PLAYER_IMG = ".playerCardThumb .img img[src]"

