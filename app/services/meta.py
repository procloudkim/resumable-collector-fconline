"""
meta.py — 메타 캐시 & 이름 검색
- /static/fconline/meta/*.json 캐시
- spid→이름, 이름→spid(정규화) 검색
- 포지션/매치타입 등 코드 맵 로딩
"""
from __future__ import annotations
from pathlib import Path
from typing import Dict, List, Any, Optional
from functools import lru_cache
import json, time, requests, re, unicodedata

from app.core.utils import log, META, DATA

BASE = "https://open.api.nexon.com"
ENDPOINTS = {
    "spid":       "/static/fconline/meta/spid.json",
    "seasonid":   "/static/fconline/meta/seasonid.json",
    "spposition": "/static/fconline/meta/spposition.json",
    "matchtype":  "/static/fconline/meta/matchtype.json",
    "division":   "/static/fconline/meta/division.json",
}

def _ensure_meta(): META.mkdir(parents=True, exist_ok=True)
def _age_hours(path: Path) -> float: return (time.time() - path.stat().st_mtime)/3600.0

def _download_json(url: str, path: Path, timeout: int = 15) -> Any:
    log(f"메타 다운로드: {url}")
    r = requests.get(url, timeout=timeout)
    r.raise_for_status()
    obj = r.json()
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    return obj

def _load_local(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))

def load_meta(name: str, *, force: bool=False, ttl_hours: Optional[int]=24*30) -> Any:
    _ensure_meta()
    if name not in ENDPOINTS: raise KeyError(f"지원되지 않는 메타: {name}")
    path = META / f"{name}.json"
    url = BASE + ENDPOINTS[name]
    if path.exists() and not force:
        if ttl_hours is None or _age_hours(path) <= ttl_hours:
            return _load_local(path)
    try:
        return _download_json(url, path)
    except requests.RequestException as e:
        log(f"메타 다운로드 실패: {e} → 캐시 사용", level="WARN")
        if path.exists(): return _load_local(path)
        raise

@lru_cache(maxsize=1)
def load_spid_map(ttl_hours: Optional[int]=24*30) -> Dict[int, Dict[str, Any]]:
    raw = load_meta("spid", ttl_hours=ttl_hours)
    out: Dict[int, Dict[str, Any]] = {}
    if isinstance(raw, list):
        for row in raw:
            spid = row.get("id") or row.get("spid")
            if spid is None: continue
            out[int(spid)] = {
                "name_kor": row.get("name_kor") or row.get("name"),
                "name_eng": row.get("name_eng") or row.get("name_en"),
                "raw": row
            }
    elif isinstance(raw, dict):
        for k, v in raw.items():
            try:
                out[int(k)] = {"name_kor": v, "name_eng": None, "raw": {"id": int(k), "name": v}}
            except Exception:
                pass
    return out

def get_player_name(spid: int, locale_keys=("name_kor","name_eng")) -> str:
    m = load_spid_map()
    row = m.get(int(spid))
    if not row: return str(spid)
    for k in locale_keys:
        if row.get(k): return str(row[k])
    return str(spid)

# 이름 정규화 & 검색
_re_space_punct = re.compile(r"[\s\W_]+", flags=re.UNICODE)

def normalize_name(name: str) -> str:
    if not name: return ""
    s = name.lower()
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = _re_space_punct.sub("", s)
    return s

@lru_cache(maxsize=1)
def build_name_index() -> Dict[str, List[int]]:
    idx: Dict[str, List[int]] = {}
    table = load_spid_map()
    for spid, row in table.items():
        for key in ("name_kor","name","name_eng"):
            nm = row.get(key)
            if not nm: continue
            k = normalize_name(str(nm))
            if not k: continue
            idx.setdefault(k, []).append(int(spid))
    return idx

def search_player_by_name(query: str, *, fuzzy: bool=False, limit: int=20) -> List[int]:
    if not query: return []
    idx = build_name_index()
    k = normalize_name(query)
    if k in idx: return idx[k][:limit]
    if fuzzy:
        out: List[int] = []
        for key, spids in idx.items():
            if k in key:
                out.extend(spids)
                if len(out) >= limit: break
        return list(dict.fromkeys(out))[:limit]
    return []

# 포지션/매치타입/디비전 코드 맵
def load_position_map(ttl_hours: Optional[int]=24*30) -> Dict[int,str]:
    raw = load_meta("spposition", ttl_hours=ttl_hours)
    out: Dict[int,str] = {}
    if isinstance(raw, list):
        for row in raw:
            code = row.get("spposition") or row.get("id") or row.get("code")
            name = row.get("desc") or row.get("name")
            if code is not None and name:
                out[int(code)] = str(name)
    return out

def load_matchtype_map(ttl_hours: Optional[int]=24*30) -> Dict[int,str]:
    raw = load_meta("matchtype", ttl_hours=ttl_hours)
    out: Dict[int,str] = {}
    if isinstance(raw, list):
        for row in raw:
            code = row.get("matchtype") or row.get("code") or row.get("id")
            name = row.get("desc") or row.get("name")
            if code is not None and name:
                out[int(code)] = str(name)
    return out

def load_division_map(ttl_hours: Optional[int]=24*30) -> Dict[int,str]:
    raw = load_meta("division", ttl_hours=ttl_hours)
    out: Dict[int,str] = {}
    if isinstance(raw, list):
        for row in raw:
            code = row.get("divisionId") or row.get("id") or row.get("code")
            name = row.get("divisionName") or row.get("desc") or row.get("name")
            if code is not None and name:
                out[int(code)] = str(name)
    return out

# spid → pid(하위 6자리) 변환 유틸 (이미지 경로용)
def spid_to_pid(spid: int) -> int:
    return int(spid) % 1_000_000
