from pathlib import Path
import pandas as pd


OUT_DIR = Path("analytics/new_analytics")
BESTPRICE = OUT_DIR / "best_price_daily.clean.names.strip.fixed.csv"
TOPDAILY = OUT_DIR / "top_daily_record.clean.ko.strip.fixed.csv"
OUT_MD = OUT_DIR / "EDA.md"


def dtype_ko(dtype: str) -> str:
    s = str(dtype)
    return {
        "object": "문자열",
        "int64": "정수",
        "float64": "실수",
        "bool": "불리언",
        "datetime64[ns]": "날짜/시간",
    }.get(s, s)


def format_shape(df: pd.DataFrame) -> str:
    return f"{df.shape[0]:,}행 × {df.shape[1]:,}열"


def try_parse_dates(df: pd.DataFrame, candidates: list[str]) -> tuple[str | None, pd.Series | None]:
    for col in candidates:
        if col in df.columns:
            s = pd.to_datetime(df[col], errors="coerce")
            if s.notna().any():
                return col, s
    return None, None


def head_table(df: pd.DataFrame, n: int = 5) -> str:
    sample = df.head(n)
    return "```text\n" + sample.to_string(index=False) + "\n```"


def column_info(df: pd.DataFrame) -> str:
    lines = ["- 컬럼 요약 (이름: 자료형)"]
    for col, dt in df.dtypes.items():
        lines.append(f"  - {col}: {dtype_ko(str(dt))}")
    return "\n".join(lines)


def top_counts(df: pd.DataFrame, col: str, n: int = 10) -> str:
    vc = df[col].value_counts().head(n)
    if vc.empty:
        return "(값 없음)"
    tbl = vc.reset_index().rename(columns={"index": col, col: "건수"})
    return "```text\n" + tbl.to_string(index=False) + "\n```"


def build_bestprice_section(df: pd.DataFrame) -> str:
    name_col = "선수의이름" if "선수의이름" in df.columns else None
    date_col, dates = try_parse_dates(df, ["date", "날짜"])  # 두 경우 모두 시도

    parts = []
    parts.append("## 1) 시세 데이터 (best_price_daily.clean.names.strip.fixed.csv)")
    parts.append(f"- 크기(Shape): {format_shape(df)}")
    parts.append(column_info(df))
    if date_col is not None:
        parts.append(f"- 수집 기간: {dates.min().date()} ~ {dates.max().date()} (기준 컬럼: {date_col})")
    if name_col:
        # 원본 player_name과 비교 (정상화 변화량)
        changed = (df["player_name"].astype(str) != df[name_col].astype(str)).sum()
        parts.append(f"- 이름 정규화로 변경된 행 수: {changed:,}건 (player_name → 선수의이름)")
        parts.append("- 선수 이름 상위 10명 (행 수 기준)")
        parts.append(top_counts(df, name_col))

    # 시즌 상위
    if "season_code" in df.columns:
        parts.append("- 시즌 상위 10개 (행 수 기준)")
        parts.append(top_counts(df, "season_code"))

    # 미리보기
    parts.append("- 데이터 미리보기(앞 5행)")
    preview_cols = [c for c in ["date", "날짜", "spid", "player_name", "선수의이름", "season_code", "position", "ovr", "price_text"] if c in df.columns]
    parts.append(head_table(df[preview_cols], 5))

    return "\n\n".join(parts)


def build_topdaily_section(df: pd.DataFrame) -> str:
    name_col = "선수의이름" if "선수의이름" in df.columns else None
    date_col, dates = try_parse_dates(df, ["날짜", "date"])  # 한글 헤더 우선

    parts = []
    parts.append("## 2) 사용률/활약 데이터 (top_daily_record.clean.ko.strip.fixed.csv)")
    parts.append(f"- 크기(Shape): {format_shape(df)}")
    parts.append(column_info(df))
    if date_col is not None:
        parts.append(f"- 수집 기간: {dates.min().date()} ~ {dates.max().date()} (기준 컬럼: {date_col})")
    if name_col:
        parts.append("- 선수 이름 상위 10명 (행 수 기준)")
        parts.append(top_counts(df, name_col))
    if "포지션" in df.columns:
        parts.append("- 포지션 상위 10개 (행 수 기준)")
        parts.append(top_counts(df, "포지션"))

    # 미리보기
    preview_cols = [c for c in ["날짜", "rank", "선수_기본정보", "포지션", "오버롤", "급여", "평점", "선수의이름"] if c in df.columns]
    parts.append("- 데이터 미리보기(앞 5행)")
    parts.append(head_table(df[preview_cols], 5))

    return "\n\n".join(parts)


def build_usage_section() -> str:
    return (
        "## 3) 분석/대시보드 적용 가이드\n"
        "- 표기/그룹핑 기준은 항상 `선수의이름` 컬럼을 사용합니다.\n"
        "- 기존 코드에서 `player_name`으로 그룹핑했다면 `선수의이름`으로 교체하세요.\n\n"
        "예시 (Pandas)\n\n"
        "```python\n"
        "import pandas as pd\n"
        "best = pd.read_csv('analytics/new_analytics/best_price_daily.clean.names.strip.fixed.csv', encoding='utf-8-sig')\n"
        "top = pd.read_csv('analytics/new_analytics/top_daily_record.clean.ko.strip.fixed.csv', encoding='utf-8-sig')\n\n"
        "# 1) 선수별 시세 평균\n"
        "best_player_price = (\n"
        "    best.groupby('선수의이름', dropna=False)['price_value']\n"
        "        .mean()\n"
        "        .reset_index(name='평균_시세')\n"
        ")\n\n"
        "# 2) 선수별 출전 기록 수\n"
        "top_player_appear = (\n"
        "    top.groupby('선수의이름', dropna=False).size()\n"
        "       .reset_index(name='기록_건수')\n"
        ")\n\n"
        "# 3) 두 데이터 결합 (선수 이름 기준)\n"
        "merged = pd.merge(best_player_price, top_player_appear, on='선수의이름', how='outer')\n"
        "```\n\n"
        "- 주의: 내부 식별/조인은 `spid`를 쓰는 것이 가장 안전합니다. 다만 사용자 표기/집계는 `선수의이름`을 권장합니다."
    )


def main():
    assert BESTPRICE.exists(), f"Missing: {BESTPRICE}"
    assert TOPDAILY.exists(), f"Missing: {TOPDAILY}"

    best = pd.read_csv(BESTPRICE, encoding="utf-8-sig", low_memory=False)
    top = pd.read_csv(TOPDAILY, encoding="utf-8-sig", low_memory=False)

    md_parts = []
    md_parts.append("# EDA 요약 (new_analytics)")
    md_parts.append(
        "본 문서는 비전공자도 이해할 수 있도록, 데이터의 크기(Shape), 컬럼, 기본 통계, 활용 가이드를 간단하고 직관적으로 정리했습니다.\n\n"
        "- 데이터는 모두 사람이 읽을 수 있는 이름 컬럼 `선수의이름`을 포함합니다.\n"
        "- 원본의 금액 단위 표기(예: `3,770조`, `1조`)나 괄호 표기는 제거되어 동일 인물을 하나로 묶을 수 있습니다.\n"
    )

    md_parts.append(build_bestprice_section(best))
    md_parts.append(build_topdaily_section(top))
    md_parts.append(build_usage_section())

    OUT_MD.write_text("\n\n".join(md_parts), encoding="utf-8")


if __name__ == "__main__":
    main()
