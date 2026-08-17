from __future__ import annotations

"""
DOM 파서(카드형 bestPrice)

WHY: 표형 데이터가 불안정해도 카드형 슬라이드에서는 핵심 정보가 안정적으로 노출된다.
HOW: 견고한 선택자와 백업 경로를 사용해 SPID/이름/시즌/포지션/OVR/급여/강화/가격/이미지/로고 코드를 추출한다.
     비표준 속성(heaf, data-season 등)은 치환하지 않고 DOM 그대로 존중한다.
"""

import re
from typing import List, Optional, Dict, Any
from urllib.parse import urlparse, parse_qs

# BeautifulSoup는 테스트에서 픽스처가 없으면 호출되지 않도록 지연 import 한다.

from .price_parser import korean_money_to_int
from . import selectors as S


def _text(node) -> str:
    return (node.get_text(" ") if node else "").strip()


def _maybe_int(node) -> Optional[int]:
    s = _text(node)
    m = re.search(r"\d+", s)
    return int(m.group(0)) if m else None


def _spid_from_href(node) -> Optional[int]:
    if not node:
        return None
    href = node.get("href") or ""
    try:
        q = parse_qs(urlparse(href).query)
        v = q.get("spid", [None])[0]
        return int(v) if v else None
    except Exception:
        return None


def _spid_from_img_src(img_src: str) -> Optional[int]:
    # playersAction/p<ID>.png 또는 players/p<ID>.png
    m = re.search(r"/p(\d+)\.png", img_src)
    return int(m.group(1)) if m else None


def _season_code_from_src(src: str) -> Optional[str]:
    # 시즌 이미지는 보통 .../season/<CODE>.png 또는 파일명 자체에 코드가 표시됨
    m = re.search(r"/season/([A-Za-z0-9_\-]+)\.png", src)
    return (m.group(1).upper() if m else None)


def _season_code_from_class(c) -> Optional[str]:
    # playerCardWrap _ICON 형태 클래스에서 코드 추정(보조)
    classes = c.get("class", []) if c else []
    for cl in classes:
        if cl.startswith("_"):
            return cl[1:].upper()
    return None


def _logo_code_from_src(src: str) -> Optional[str]:
    # 예: countries/smallflags/{code}.png, league/.../l{code}.png 등 → 파일명 추출
    m = re.search(r"/([A-Za-z0-9_\-]+)\.png", src)
    return (m.group(1).upper() if m else None)


def parse_bestprice_cards(html: str, date_str: str) -> List[Dict[str, Any]]:
    """
    WHY: 카드형에서 필요한 모든 필드를 최대한 수집하고, 일부 필드는 None으로 보존한다.
    HOW: 선택자 우선순위(SPID→이름→가격→강화...)에 따라 추출한다.
    """
    # 지연 import (pytest 실행 환경에서 beautifulsoup4 미설치 시 import 오류 방지)
    from bs4 import BeautifulSoup  # type: ignore

    soup = BeautifulSoup(html or "", "lxml")
    cards = soup.select(S.CARDS)
    out: List[Dict[str, Any]] = []
    for c in cards:
        # SPID
        a = c.select_one(S.SPID_LINK)
        spid = _spid_from_href(a)

        # 이미지 URL / SPID 백업
        img_node = c.select_one(S.PLAYER_IMG)
        img_url = img_node.get("src") if img_node and img_node.has_attr("src") else None
        if not spid and img_url:
            spid = _spid_from_img_src(img_url)
        if not spid:
            continue  # 키 없으면 스킵

        # 이름
        name_node = c.select_one(S.NAME)
        name = _text(name_node)
        if not name:
            name_hidden = c.select_one(S.NAME_HIDDEN)
            name = _text(name_hidden)

        # 시즌 코드
        season_img = c.select_one(S.SEASON_IMG)
        season_code = _season_code_from_src(season_img.get("src")) if season_img else None
        if not season_code:
            wrap = c.select_one(".playerCardWrap")
            season_code = _season_code_from_class(wrap)

        # 포지션/OVR/급여/강화
        position = _text(c.select_one(S.POSITION)).upper() or None
        ovr = _maybe_int(c.select_one(S.OVR))
        pay = _maybe_int(c.select_one(S.PAY))

        enh_node = c.select_one(S.ENHANCE)
        enhance = _maybe_int(enh_node)
        if enhance is None and a is not None:
            href = a.get("href") or ""
            try:
                q = parse_qs(urlparse(href).query)
                v = q.get("n1Strong", [None])[0]
                enhance = int(v) if v else None
            except Exception:
                pass

        # 가격(원문 + 정수)
        price_node = c.select_one(S.PRICE)
        price_text = None
        price_value = None
        if price_node is not None:
            for attr in ("alt", "title"):
                v = price_node.get(attr)
                if v:
                    price_text = str(v).strip()
                    price_value = korean_money_to_int(price_text)
                    break
            if price_value is None:
                price_text = _text(price_node)
                price_value = korean_money_to_int(price_text)
        # 이상치/0 방지: 음수/0이면 None
        if isinstance(price_value, int) and price_value <= 0:
            price_value = None

        # 로고 코드(페이지마다 존재 안할 수 있음 → 코드만 수집)
        nation_img = soup.select_one(".playerCardInfoSort .nation img[src]")
        league_img = soup.select_one(".playerCardInfoSort .league img[src]")
        team_img = soup.select_one(".playerCardInfoSort .team img[src]")
        nation_code = _logo_code_from_src(nation_img.get("src")) if nation_img else None
        league_code = _logo_code_from_src(league_img.get("src")) if league_img else None
        team_code = _logo_code_from_src(team_img.get("src")) if team_img else None

        out.append(
            {
                "date": date_str,
                "spid": spid,
                "player_name": name or None,
                "season_code": season_code,
                "position": position,
                "ovr": ovr,
                "pay": pay,
                "enhance": enhance,
                "price_value": price_value,
                "price_text": price_text,
                "player_image_url": img_url,
                "nation_code": nation_code,
                "league_code": league_code,
                "team_code": team_code,
            }
        )
    return out

