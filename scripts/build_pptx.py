from __future__ import annotations

"""
이미 생성된 발표용 이미지(analytics/exports)를 모아 PPTX를 자동 생성합니다.

요구 패키지: python-pptx (없으면 안내 후 스크립트 종료)

출력: analytics/exports/FinalDeck.pptx

추가 옵션
- --template: 회사 템플릿 PPTX(또는 POTX) 경로 지정 시 해당 마스터/테마 사용
- --brand-font: 기본 폰트 지정(기본 'Malgun Gothic')
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPORTS = ROOT / "analytics" / "exports"


def main() -> int:
    try:
        from pptx import Presentation  # type: ignore
        from pptx.util import Inches, Pt  # type: ignore
        from pptx.dml.color import RGBColor  # type: ignore
    except Exception:
        print("[ERROR] python-pptx가 설치되어 있지 않습니다.\n"
              "설치: python -m pip install python-pptx")
        return 2

    import argparse
    ap = argparse.ArgumentParser(description="이미지 → PPTX 자동 생성")
    ap.add_argument("--template", type=str, default="", help="회사 템플릿 PPTX/POTX 경로")
    ap.add_argument("--brand-font", type=str, default="Malgun Gothic", help="기본 폰트")
    args = ap.parse_args()

    if args.template and (ROOT / args.template).exists():
        prs = Presentation(str(ROOT / args.template))
    else:
        prs = Presentation()

    def set_textbox_font(tb, font_name: str = args.brand_font, size: int | None = None, bold: bool | None = None):
        try:
            for p in tb.text_frame.paragraphs:
                for r in p.runs:
                    r.font.name = font_name
                    if size:
                        r.font.size = Pt(size)
                    if bold is not None:
                        r.font.bold = bold
        except Exception:
            pass

    def add_title_slide(title: str, subtitle: str = "") -> None:
        slide_layout = prs.slide_layouts[0]
        slide = prs.slides.add_slide(slide_layout)
        slide.shapes.title.text = title
        set_textbox_font(slide.shapes.title, size=40, bold=True)
        if subtitle:
            slide.placeholders[1].text = subtitle
            set_textbox_font(slide.placeholders[1], size=18, bold=False)

    def add_image_slide(title: str, img_path: Path) -> None:
        slide_layout = prs.slide_layouts[5]  # Title Only
        slide = prs.slides.add_slide(slide_layout)
        slide.shapes.title.text = title
        set_textbox_font(slide.shapes.title, size=28, bold=True)
        left = Inches(0.5)
        top = Inches(1.5)
        width = Inches(9.0)
        if img_path.exists():
            slide.shapes.add_picture(str(img_path), left, top, width=width)
        else:
            slide.shapes.title.text = f"{title} (이미지 없음)"

    def add_text_slide(title: str, text: str) -> None:
        slide_layout = prs.slide_layouts[1]  # Title and Content
        slide = prs.slides.add_slide(slide_layout)
        slide.shapes.title.text = title
        set_textbox_font(slide.shapes.title, size=28, bold=True)
        tf = slide.placeholders[1].text_frame
        for i, line in enumerate(text.splitlines()):
            if i == 0:
                tf.text = line
            else:
                p = tf.add_paragraph()
                p.text = line
                p.level = 0
        set_textbox_font(slide.placeholders[1], size=16, bold=False)

    # 커버
    cover = EXPORTS / "cover_landscape.png"
    if cover.exists():
        add_image_slide("커버", cover)
    else:
        add_title_slide("FC 온라인 통합 분석", "발표 자료")

    # 메타/가격/임팩트/감성/상관
    add_image_slide("메타 TopN (최근 연도)", EXPORTS / "meta_topn_year_landscape.png")
    add_image_slide("거래 가격 TopN (최근 연도)", EXPORTS / "price_topn_year_landscape.png")
    add_image_slide("빅매치 임팩트(±윈도우)", EXPORTS / "event_impact_landscape.png")
    add_image_slide("유튜브 감성 분포", EXPORTS / "sentiment_dist_landscape.png")
    add_image_slide("감성–출전 상관", EXPORTS / "sentiment_play_corr_landscape.png")

    # 요약 통계 텍스트
    stats_path = EXPORTS / "summary_stats.txt"
    if stats_path.exists():
        add_text_slide("기술통계 요약", stats_path.read_text(encoding="utf-8"))

    # 결론/섹션 카드 있으면 추가
    for title, name in [("요약", "section_summary_landscape.png"), ("결론", "section_conclusion_landscape.png")]:
        p = EXPORTS / name
        if p.exists():
            add_image_slide(title, p)

    out = EXPORTS / "FinalDeck.pptx"
    prs.save(str(out))
    print(f"[THEN] PPTX 저장: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
