Changelog
=========

v1.0.0 (2025-09-13)
-------------------
- Docs: README 상단 5줄 요약 추가, RUNBOOK/CODEMAP/FAQ 신설
- Repro: `.env.example`, `scripts/bootstrap.ps1`(setup/demo/fetch), `requirements.lock` 추가
- Sample: `scripts/demo_data.py`, `data/sample/top10_trend.sample.csv`
- Observability: 구조화 로그(JSON) 유틸, 대시보드 헬스/다운로드/기간 필터
- Tests: `tests/test_smoke.py`, `pytest.ini`(marker 등록)
- Governance: 데이터 사전/품질/출처/타임존/프라이버시 문서 추가
- Security: `.pre-commit-config.yaml`(detect-secrets), 정책 문서 명시


v1.1.0 (2025-09-14)
-------------------
- Docs: project2 문서 세트 추가 및 링크 보강
  - 신규: docs/PROJECT2_RUNBOOK_KR.md, docs/PROJECT2_PRD_KR.md, docs/PROJECT2_BDD_KR.md, docs/PROJECT2_ERD_KR.md,
          docs/LOCAL_ARCHITECTURE_OVERVIEW_KR.md, docs/CODE_TECHNICAL_SUMMARY_KR.md,
          docs/INDEX.md, docs/TROUBLESHOOTING_KR.md, docs/ENCODING_POLICY.md
  - 보강: docs/STRUCTURE.md, docs/LOGGING.md, docs/ERD.md(출전 랭킹 ERD 링크)
  - 루트: README.md에 project2 문서 링크 섹션 추가
  - 안내: CONTRIBUTING.md 추가
  - Note: 코드/DB 변경 없음 (문서만 업데이트)
