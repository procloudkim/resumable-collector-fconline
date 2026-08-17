"""
utils.py — 경로/로거/.env 로딩
- 모든 스크립트가 공용 경로(ROOT/DATA/RAW/PROC/META/IMAGES)를 공유
- .env 로딩(있으면) + 환경변수 헬퍼 + 간단 로거
"""
from __future__ import annotations
from pathlib import Path
import os, time, json

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

# 통합 API 키 로더: Streamlit secrets 우선 → 환경변수
def get_api_key(var: str = "NEXON_OPENAPI_API_KEY") -> str | None:
    """
    Streamlit이 가능하면 `st.secrets[var]`를 먼저 조회하고,
    없거나 Streamlit이 없는 환경에서는 `os.getenv(var)`를 반환한다.
    .env는 모듈 상단에서 load_dotenv()로 이미 로딩 시도함.
    """
    try:
        import streamlit as st  # type: ignore
        # st.secrets는 Mapping-like. 키가 없으면 None 반환 안전 처리
        v = None
        try:
            v = st.secrets.get(var)  # type: ignore[attr-defined]
        except Exception:
            v = None
        if v:
            return str(v)
    except Exception:
        # Streamlit이 없는 CLI 환경 등
        pass
    return os.getenv(var)

# Backward-compat: expose API_KEY constant for legacy scripts/tests
# WHY: 일부 스크립트/테스트가 utils.API_KEY를 직접 참조
# WHAT: .env/환경변수/Streamlit secrets에서 읽은 값을 모듈 레벨 상수로 노출
# HOW: 모듈 임포트 시점에 한 번 평가
API_KEY: str | None = get_api_key()

# 경로 상수
ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
RAW = DATA / "raw"
PROC = DATA / "processed"
META = DATA / "meta"
IMAGES = DATA / "images"

def ensure_dirs() -> None:
    for p in (DATA, RAW, PROC, META, IMAGES):
        p.mkdir(parents=True, exist_ok=True)

def ts() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")

def log(msg: str, level: str = "INFO") -> None:
    print(f"[{ts()}][{level}] {msg}", flush=True)

def get_env(key: str, default: str | None = None) -> str | None:
    """환경변수 헬퍼(.env → os.environ)"""
    v = os.getenv(key, default)
    return v

def jlog(event: str, **fields: object) -> None:
    """Structured logging to logs/app.log as JSON lines.

    Fields: timestamp(ts), module, event, status, latency_ms, rows, etc.
    Secrets must never be logged.
    """
    try:
        out = {"ts": ts(), "module": __name__, "event": event}
        out.update(fields)
        log_dir = (Path(__file__).resolve().parents[2] / "logs")
        log_dir.mkdir(parents=True, exist_ok=True)
        with (log_dir / "app.log").open("a", encoding="utf-8") as fo:
            fo.write(json.dumps(out, ensure_ascii=False) + "\n")
    except Exception:
        # Fallback to plain log on any failure
        log(f"event={event} fields={fields}")
