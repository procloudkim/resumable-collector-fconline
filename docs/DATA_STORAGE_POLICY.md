Data Storage Policy (Git/LFS)
=============================

- 제외(.gitignore): 운영 데이터/이미지 — `data/raw/`, `data/images/`, `data/**/*.db`
- 허용: 파생 CSV(`data/processed/`) 중 핵심 요약(`top10_trend.csv`)만 추적
- 스냅샷: 공유가 필요한 DB는 `data/snapshots/`에 두고 Git LFS 속성 적용(`.gitattributes`)
- 재현: 필요 시 `scripts/demo_data.py`로 샘플 생성 또는 파이프라인 재실행

