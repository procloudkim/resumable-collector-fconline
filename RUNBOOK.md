FC Online Analytics — RUNBOOK (운영 요약)
=======================================

핵심 흐름
---------
- 설치 → .env 채움 → 원클릭 데모 →(선택) 실데이터 수집 → 대시보드 확인 → 문제 발생 시 복구.

사전 준비(1회)
--------------
- Windows PowerShell 권장. 저장소 루트에서 실행.
- Python 3.10+ 권장. 기본 의존성은 `requirements.txt`.

원클릭 태스크
------------
- Setup: 가상환경 생성, 의존성 설치, 샘플 데이터 준비
  - `pwsh -File scripts/bootstrap.ps1 -Task setup`
- Demo: 샘플 데이터로 대시보드 실행(오프라인 가능)
  - `pwsh -File scripts/bootstrap.ps1 -Task demo`
- Fetch: 실데이터 수집 파이프라인(네트워크/키 필요)
  - `pwsh -File scripts/bootstrap.ps1 -Task fetch`

.env 채우기
-----------
1) `.env.example`를 `.env`로 복사
2) `NEXON_OPENAPI_API_KEY`에 발급 키 입력

대시보드
--------
- 수동 실행: `streamlit run app/dashboard.py`
- 상단 배지: 마지막 수집 시각/DB 건수/CSV 행수 표시(헬스체크)
- UI: 새로고침(데모/실행), 기간 필터, CSV 다운로드 버튼 제공

문제 해결
--------
- 의존성 꼬임: `.venv` 제거 후 `-Task setup` 재실행
- 키 누락: `.env` 혹은 `.streamlit/secrets.toml` 확인
- 레이아웃 변경: `docs/check/DOM_REPORT.md` 참조 후 셀렉터 업데이트

복구/청소
--------
- 로그 정리: `logs/` 폴더 삭제 가능(보존 필요 시 압축)
- 데이터 초기화: `data/data.db` 백업/삭제, `scripts/demo_data.py`로 샘플 재주입

검증
----
- 스모크: `pytest -q -m smoke` (10초 내)

