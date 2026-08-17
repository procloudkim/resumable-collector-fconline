"""
top_daily_record.clean.csv 컬럼 한글화 + '선수_기본정보' 파싱 유틸리티

요구사항
- 컬럼명 변경:
  - date -> 날짜
  - 선수_기본정보 -> 선수_기본정보(동일 유지)
  - 출전 -> 출전_기록
  - 공격 -> 공격
  - 패스 -> 패스
  - 수비 -> 수비
  - 태클성공률 -> 태클_성공률
  - (그 외 제시된 컬럼명은 동일 표기로 유지)
- '선수_기본정보' 파싱:
  - 형식: '선수명, 강화 단계, 포지션, 오버롤, 급여' (쉼표로 구분)
  - 변형 케이스 허용: 포지션+오버롤이 'ST 99' 같이 합쳐진 경우 처리
  - 생성 컬럼: '선수명'(str), '강화 단계'(int), '포지션'(str), '오버롤'(int), '급여'(int)
- 문자열 컬럼 공백 점검: 기본은 점검만, --strip-whitespace 옵션에서 일괄 제거

입출력
- 입력: analytics/clean/top_daily_record.clean.csv
- 출력 기본: analytics/clean/top_daily_record.clean.ko.csv (또는 --overwrite)
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd


RENAME_MAP: Dict[str, str] = {
    "date": "날짜",
    "선수_기본정보": "선수_기본정보",
    "출전": "출전_기록",
    "공격": "공격",
    "패스": "패스",
    "수비": "수비",
    "태클성공률": "태클_성공률",
    "공격형_점유율": "공격형_점유율",
    "역습_상황_공격점유율": "역습_상황_공격점유율",
    "점유_위치_공격_비율": "점유_위치_공격_비율",
    "위치_점유_드리블_비율": "위치_점유_드리블_비율",
    "점유_위치_위험_비율": "점유_위치_위험_비율",
    "볼_점유율": "볼_점유율",
    "평점": "평점",
}


def _to_int_safe(s: str) -> Optional[int]:
    s = str(s or "").strip()
    if not s:
        return None
    s2 = re.sub(r"[^0-9]", "", s)
    if not s2:
        return None
    try:
        return int(s2)
    except Exception:
        return None


def _parse_player_info(val: str) -> Tuple[Optional[str], Optional[int], Optional[str], Optional[int], Optional[int]]:
    """
    입력 예시: '엘링 홀란, 3, ST 99, 21' 또는 '엘링 홀란, 3, ST, 99, 21'
    반환: (선수명, 강화 단계, 포지션, 오버롤, 급여)
    """
    try:
        parts = [p.strip() for p in str(val or "").split(",")]
    except Exception:
        parts = []

    name: Optional[str] = None
    enh: Optional[int] = None
    pos: Optional[str] = None
    ovr: Optional[int] = None
    pay: Optional[int] = None

    if parts:
        name = parts[0].strip()
    if len(parts) >= 2:
        enh = _to_int_safe(parts[1])
    if len(parts) == 5:
        pos = parts[2].strip() or None
        ovr = _to_int_safe(parts[3])
        pay = _to_int_safe(parts[4])
    elif len(parts) >= 3:
        # 포지션+오버롤 합본 케이스 처리: 'ST 99'
        pos_ovr = parts[2]
        m = re.search(r"([A-Za-z]{1,3})\s*(\d{1,3})?", pos_ovr)
        if m:
            pos = (m.group(1) or "").upper() or None
            ovr = _to_int_safe(m.group(2) or "")
        if len(parts) >= 4:
            pay = _to_int_safe(parts[3])

    return name, enh, pos, ovr, pay


def localize_top_daily(
    in_path: Path = Path("analytics/clean/top_daily_record.clean.csv"),
    out_path: Optional[Path] = None,
    *,
    overwrite: bool = False,
    strip_whitespace: bool = False,
) -> Path:
    df = pd.read_csv(in_path)

    # 컬럼명 변경(존재하는 것만 적용)
    rename_applicable = {c: RENAME_MAP[c] for c in df.columns if c in RENAME_MAP}
    df = df.rename(columns=rename_applicable)

    # 선수_기본정보 파싱
    info_col = "선수_기본정보"
    if info_col in df.columns:
        parsed = df[info_col].apply(_parse_player_info)
        df["선수명"] = [t[0] for t in parsed]
        df["강화 단계"] = [t[1] for t in parsed]
        df["포지션"] = [t[2] for t in parsed]
        df["오버롤"] = [t[3] for t in parsed]
        df["급여"] = [t[4] for t in parsed]

    # 공백 점검 및 선택적 제거(이름 컬럼 제외)
    issues: Dict[str, int] = {}
    for c in df.columns:
        if pd.api.types.is_object_dtype(df[c]):
            s = df[c].astype(str)
            cnt = int(((s != s.str.strip()).sum()))
            if cnt:
                issues[c] = cnt
            if strip_whitespace and cnt:
                df[c] = s.str.strip()

    # 출력 경로 결정
    if overwrite:
        out = in_path
    else:
        out = out_path or in_path.with_name(in_path.stem + ".ko.csv")
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False, encoding="utf-8")

    # 리포트 출력(콘솔)
    if issues:
        pairs = ", ".join([f"{k}:{v}" for k, v in issues.items()])
        print(f"[WHEN] 공백 이슈 감지 => {pairs}")
        if not strip_whitespace:
            print("[THEN] 공백 제거는 적용하지 않았습니다. --strip-whitespace 옵션으로 제거할 수 있습니다.")
    else:
        print("[WHEN] 공백 이슈 없음")

    print(f"[THEN] wrote {out}")
    return out


def _parse_args():
    import argparse

    ap = argparse.ArgumentParser(description="top_daily_record.clean.csv 한글화 + 선수_기본정보 파싱")
    ap.add_argument("--in", dest="inp", default="analytics/clean/top_daily_record.clean.csv", help="입력 CSV")
    ap.add_argument("--out", dest="outp", default=None, help="출력 CSV(기본: *.ko.csv)")
    ap.add_argument("--overwrite", action="store_true", help="원본 덮어쓰기")
    ap.add_argument("--strip-whitespace", action="store_true", help="문자열 컬럼 공백 제거")
    return ap.parse_args()


def main() -> int:
    args = _parse_args()
    inp = Path(args.inp)
    outp = Path(args.outp) if args.outp else None
    localize_top_daily(in_path=inp, out_path=outp, overwrite=bool(args.overwrite), strip_whitespace=bool(args.strip_whitespace))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

