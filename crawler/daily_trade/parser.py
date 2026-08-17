from __future__ import annotations
from dataclasses import dataclass
from typing import Iterable, List, Dict, Any, Optional
import re
import unicodedata

from bs4 import BeautifulSoup

from . import setup_logger


class LayoutChangedError(RuntimeError):
    """페이지 구조 변화 감지용 예외

    표/헤더 탐지가 실패하면 상위 레벨에서 HTML을 저장하고 스킵하도록 알린다.
    """


def _normalize(s: str) -> str:
    s = (s or "").strip().lower()
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return re.sub(r"[\s\W_]+", "", s)


def price_to_int(text: Optional[str]) -> Optional[int]:
    """가격 문자열을 정수로 변환 (억/만 단위 및 콤마/접미사 허용).

    규칙:
    - "X억 Y만" -> X*1e8 + Y*1e4
    - "X억" -> X*1e8, "Y만" -> Y*1e4
    - 순수 숫자(콤마 포함) -> int
    - 접미사(BP, 원 등) 제거 후 숫자만 -> int
    - 실패 시 None
    """
    if text is None:
        return None
    s = str(text).strip()
    if not s:
        return None
    s_clean = s.replace(",", "")
    # 1) 순수 숫자
    if re.fullmatch(r"\d+", s_clean):
        try:
            return int(s_clean)
        except Exception:
            return None
    # 2) 억/만 조합
    total = 0
    matched = False
    m = re.search(r"(\d+)\s*억", s_clean)
    if m:
        total += int(m.group(1)) * 100_000_000
        matched = True
    m = re.search(r"(\d+)\s*만", s_clean)
    if m:
        total += int(m.group(1)) * 10_000
        matched = True
    if matched:
        return total
    # 3) 접미사 제거 후 숫자 추출
    digits = re.sub(r"[^0-9]", "", s_clean)
    if digits:
        try:
            return int(digits)
        except Exception:
            return None
    return None

# Override with corrected implementation (supports 조=1e12, 억=1e8)
def _price_to_int_correct(text: Optional[str]) -> Optional[int]:
    if text is None:
        return None
    s = str(text).strip()
    if not s:
        return None
    s_clean = s.replace(",", "")
    # 1) plain digits
    if re.fullmatch(r"\d+", s_clean):
        try:
            return int(s_clean)
        except Exception:
            return None
    # 2) 조/억 combo
    total = 0
    matched = False
    m = re.search(r"(\d+)\s*조", s_clean)
    if m:
        total += int(m.group(1)) * 1_000_000_000_000
        matched = True
    m = re.search(r"(\d+)\s*억", s_clean)
    if m:
        total += int(m.group(1)) * 100_000_000
        matched = True
    if matched:
        return total
    # 3) fallback: strip non-digits
    digits = re.sub(r"[^0-9]", "", s_clean)
    if digits:
        try:
            return int(digits)
        except Exception:
            return None
    return None

# point the public name to the corrected function
price_to_int = _price_to_int_correct


@dataclass
class PlayerTarget:
    spid: int
    name_kor: Optional[str] = None
    name_eng: Optional[str] = None


def _targets_index(targets: Iterable[PlayerTarget]) -> Dict[str, int]:
    idx: Dict[str, int] = {}
    for t in targets:
        if t.name_kor:
            idx[_normalize(t.name_kor)] = t.spid
        if t.name_eng:
            idx[_normalize(t.name_eng)] = t.spid
    return idx


def parse_daily_trade(html: str, date_str: str, targets: Iterable[PlayerTarget]) -> List[Dict[str, Any]]:
    """일별 거래 파싱 (표 헤더 변화에 강한 방식)

    - 표의 thead/첫행 헤더를 스캔해 컬럼 매핑
    - 실패 시 pandas.read_html()로 폴백
    - 매칭 타겟에 없는 선수는 스킵, 누락 타겟은 0/None으로 채움
    """
    logger = setup_logger()
    soup = BeautifulSoup(html, "html.parser")

    def map_headers(raw_headers: List[str]) -> Dict[str, int]:
        norm = [_normalize(x) for x in raw_headers]
        cols = {"player": -1, "avg": -1, "max": -1, "min": -1, "trade": -1, "enh": -1}
        synonyms = {
            "player": ("선수", "선수명", "플레이어", "player"),
            "avg": ("평균", "평균가", "avg", "average"),
            "max": ("최고", "최고가", "max", "high"),
            "min": ("최저", "최저가", "min", "low"),
            "trade": ("거래", "거래수", "거래량", "trade", "volume"),
            "enh": ("강화", "강화등급", "강화레벨", "+"),
        }
        for i, (n, raw) in enumerate(zip(norm, raw_headers)):
            for key, words in synonyms.items():
                if any((w in raw) or n.startswith(_normalize(w)) for w in words):
                    if cols[key] < 0:
                        cols[key] = i
        return cols

    best_table = None
    header_map: Dict[str, int] = {}
    for tb in soup.find_all("table"):
        thead = tb.find("thead")
        if thead:
            raw = [th.get_text(" ").strip() for th in thead.find_all("th")]
        else:
            first_tr = tb.find("tr")
            if not first_tr:
                continue
            raw = [th.get_text(" ").strip() for th in first_tr.find_all(["th", "td"])]
        if not raw:
            continue
        cols = map_headers(raw)
        if cols.get("player", -1) >= 0:
            best_table = tb
            header_map = cols
            logger.debug("event=header_detected headers=%s map=%s", raw, header_map)
            break

    if best_table is None:
        try:
            import pandas as pd  # type: ignore
            dfs = pd.read_html(html)
            for df in dfs:
                headers = [str(c) for c in df.columns]
                cols = map_headers(headers)
                if cols.get("player", -1) >= 0:
                    tmp_html = df.to_html(index=False)
                    tmp_soup = BeautifulSoup(tmp_html, "html.parser")
                    best_table = tmp_soup.find("table")
                    header_map = map_headers([
                        th.get_text(" ").strip() for th in best_table.find("tr").find_all(["th", "td"])
                    ])
                    break
        except Exception:
            pass

    # 2-a) Card/slider layout fallback: parse from swiper slides (최고가 거래 선수)
    if best_table is None:
        from urllib.parse import urlparse, parse_qs
        rows: List[Dict[str, Any]] = []
        slides = soup.select("#divBestTradeArea_price .swiper-slide")
        def slide_spid(slide) -> Optional[int]:
            a = slide.select_one("a.outlink[href*='PlayerInfo?spid=']")
            if not a:
                return None
            try:
                href = a.get("href") or ""
                q = parse_qs(urlparse(href).query)
                spid = q.get("spid", [None])[0]
                return int(spid) if spid else None
            except Exception:
                return None
        def slide_name(slide) -> Optional[str]:
            # Prefer explicit name nodes
            n = slide.select_one(".playerCardInfoBottom .nameWrap .name span, .player_wrap[title]")
            if n and n.get_text(" "):
                return n.get_text(" ").strip()
            if n and n.has_attr("title"):
                return str(n["title"]).strip()
            hidden = slide.select_one("a.outlink > span.hidden")
            if hidden and hidden.get_text(" "):
                return hidden.get_text(" ").strip()
            return None
        def slide_price(slide) -> Optional[int]:
            p = slide.select_one(".price_wrap .price")
            if p is not None:
                for attr in ("alt", "title"):
                    v = p.get(attr)
                    if v:
                        v2 = re.sub(r"[^0-9]", "", str(v))
                        if v2:
                            try:
                                return int(v2)
                            except Exception:
                                pass
                txt = p.get_text(" ")
                v = price_to_int(txt)
                if v is not None:
                    return v
            # Fallback to slide text
            return price_to_int(slide.get_text(" "))
        def slide_level(slide) -> Optional[int]:
            # Try explicit ability level
            a = slide.select_one(".buildUp a")
            if a and re.search(r"\d+", a.get_text(" ")):
                try:
                    return int(re.search(r"\d+", a.get_text(" ")).group(0))
                except Exception:
                    return None
            m = re.search(r"\+(\d+)", slide.get_text(" "))
            return int(m.group(1)) if m else None

        for slide in slides[:18]:  # Top 18 only
            spid = slide_spid(slide)
            if not spid:
                continue
            name = slide_name(slide)
            price = slide_price(slide)
            lvl = slide_level(slide)
            rows.append({
                "date": date_str,
                "spid": spid,
                "player_name": name,
                "avg_price": price,
                "max_price": price,
                "min_price": None,
                "trade_count": None,
                "max_enhance_level": lvl,
                "source": "web",
            })
        if rows:
            # Fill missing from targets
            found_spids = {r["spid"] for r in rows}
            all_spids = {t.spid for t in targets}
            for spid in sorted(all_spids - found_spids):
                rows.append({
                    "date": date_str,
                    "spid": spid,
                    "player_name": None,
                    "avg_price": None,
                    "max_price": None,
                    "min_price": None,
                    "trade_count": 0,
                    "max_enhance_level": None,
                    "source": "web",
                })
            logger.info(
                "event=parse_trade_done_fallback_cards date=%s rows=%d", date_str, len(rows)
            )
            return rows
        # No table and no cards
        raise LayoutChangedError("trade table not found")

    idx = _targets_index(targets)
    found_spids: set[int] = set()
    rows: List[Dict[str, Any]] = []
    for tr in best_table.find_all("tr"):
        # 헤더 (th 포함)은 스킵
        if tr.find("th"):
            continue
        tds = tr.find_all(["td", "th"])  # 어떤 표는 th를 데이터셀로 씀
        if not tds:
            continue
        try:
            name = tds[header_map["player"]].get_text(" ").strip()
        except Exception:
            continue
        key = _normalize(name)
        spid = idx.get(key)
        if not spid:
            continue

        pidx = header_map.get("player", -1)
        count = len(tds)

        def pick_idx(primary: int, fallback: int) -> int:
            return primary if 0 <= primary < count else (fallback if 0 <= fallback < count else -1)

        avg_i = pick_idx(header_map.get("avg", -1), pidx + 1)
        max_i = pick_idx(header_map.get("max", -1), pidx + 2)
        min_i = pick_idx(header_map.get("min", -1), pidx + 3)
        trade_i = pick_idx(header_map.get("trade", -1), pidx + 4)
        enh_i = pick_idx(header_map.get("enh", -1), pidx + 5)

        avg_text = tds[avg_i].get_text(" ").strip() if avg_i >= 0 else None
        max_text = tds[max_i].get_text(" ").strip() if max_i >= 0 else None
        min_text = tds[min_i].get_text(" ").strip() if min_i >= 0 else None
        trade_text = tds[trade_i].get_text(" ").strip() if trade_i >= 0 else None
        enh_text = tds[enh_i].get_text(" ").strip() if enh_i >= 0 else None

        def parse_level(s: Optional[str]) -> Optional[int]:
            if not s:
                return None
            m = re.search(r"\+(\d+)", s)
            return int(m.group(1)) if m else None

        level = parse_level(enh_text)
        if level is None:
            # Fallback: scan the entire row text for +<n>
            level = parse_level(tr.get_text(" "))

        rec = {
            "date": date_str,
            "spid": spid,
            "player_name": name,
            "avg_price": price_to_int(avg_text),
            "max_price": price_to_int(max_text),
            "min_price": price_to_int(min_text),
            "trade_count": int(re.sub(r"[^0-9]", "", trade_text)) if trade_text and re.search(r"\d", trade_text) else None,
            "max_enhance_level": level,
            "source": "web",
        }
        rows.append(rec)
        found_spids.add(spid)

    # 누락된 타겟은 거래수=0, 가격=None 으로 채움
    all_spids = {t.spid for t in targets}
    for spid in sorted(all_spids - found_spids):
        rows.append({
            "date": date_str,
            "spid": spid,
            "player_name": None,
            "avg_price": None,
            "max_price": None,
            "min_price": None,
            "trade_count": 0,
            "max_enhance_level": None,
            "source": "web",
        })
    logger.info(
        "event=parse_trade_done date=%s targets=%d found=%d filled_missing=%d rows=%d",
        date_str, len(all_spids), len(found_spids), len(all_spids - found_spids), len(rows),
    )
    return rows


def parse_daily_top_players(html: str, date_str: str) -> List[Dict[str, Any]]:
    """일별 TopN 선수 파싱 (간단 표 기반)

    표가 없으면 빈 리스트를 반환하고 상위에서 CSV만 보조 저장할 수 있다.
    """
    logger = setup_logger()
    soup = BeautifulSoup(html, "html.parser")
    tables = soup.find_all("table")
    if not tables:
        raise LayoutChangedError("no table found")
    best_table = None
    for tb in tables:
        txt = (tb.get_text(" ") or "").lower()
        if ("top" in txt) or ("pick" in txt) or ("픽" in txt):
            best_table = tb
            break
    if best_table is None:
        logger.warning("event=topn_table_missing date=%s", date_str)
        return []

    def as_float_percent(s: str) -> Optional[float]:
        s = s.strip().replace("%", "")
        return float(s) if s and re.fullmatch(r"[0-9.]+", s) else None

    rows: List[Dict[str, Any]] = []
    for tr in best_table.find_all("tr"):
        if tr.find("th"):
            continue
        tds = tr.find_all(["td", "th"])
        if len(tds) < 3:
            continue
        try:
            rank = int(re.sub(r"[^0-9]", "", tds[0].get_text(" "))) if re.search(r"\d", tds[0].get_text()) else None
            name = tds[1].get_text(" ").strip()
            pick_rate = as_float_percent(tds[2].get_text(" "))
        except Exception:
            continue
        rows.append({
            "date": date_str,
            "spid": None,
            "rank": rank,
            "pick_rate": pick_rate,
            "player_name": name,
        })
    logger.info("event=parse_topn_done date=%s rows=%d", date_str, len(rows))
    return rows


__all__ = [
    "LayoutChangedError",
    "PlayerTarget",
    "price_to_int",
    "parse_daily_trade",
    "parse_daily_top_players",
]
