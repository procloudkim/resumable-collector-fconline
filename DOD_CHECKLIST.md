Definition of Done (DoD) — 제출 전 점검표
=========================================

- README 상단 5줄 요약 확인(목적·산출물·데모·출처·면책)
- 원클릭 데모: `scripts/bootstrap.ps1 -Task demo` 정상 실행
- 샘플 데이터 포함(`data/sample/*`), 대시보드 오프라인 표시
- 스모크 테스트 통과: `pytest -q -m smoke`
- 라이선스/데이터 출처 명확화: `LICENSE`, `DATA_LICENSE.md`
- 문서: RUNBOOK, CODEMAP, FAQ, 데이터 딕셔너리/품질/출처/타임존/프라이버시
- 보안: 키 `.env`만 사용, `.pre-commit` detect-secrets 구성
- 태그: v1.0.0 릴리스 노트(`CHANGELOG.md`), 발표자료 아웃라인/데모 스크립트

