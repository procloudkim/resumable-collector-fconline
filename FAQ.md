FAQ — 자주 묻는 질문
====================

- 왜 HTML 크롤링과 Open API를 혼용하나요?
  - Open API로 제공되지 않는 지표/랭킹/최신 시세 일부는 웹에만 존재합니다. API는 신뢰성·구조화 장점이, HTML은 최신성/보완재 역할이 있어 혼합이 최적입니다.

- 이미지를 왜 Git 추적에서 제외하나요?
  - 이미지(`data/images/*.png`)는 용량이 크고 빈번히 변합니다. 저장소 팻화 방지를 위해 `.gitignore`로 제외하고, 필요 시 로컬 캐시/재다운로드로 재현합니다.

- DB 파일은 어떻게 관리하나요?
  - 운영 DB는 추적 제외(`data/**/*.db`). 공유가 필요한 스냅샷만 `data/snapshots/`에 LFS로 보관합니다. 자세한 정책은 `docs/DATA_STORAGE_POLICY.md` 참고.

- Streamlit에서 키는 어디에 넣나요?
  - 로컬은 `.env`(`NEXON_OPENAPI_API_KEY`)를, 배포는 `/.streamlit/secrets.toml`을 사용합니다. 코드·로그에 키가 출력되지 않도록 주의했습니다.

- 오프라인 데모가 가능한가요?
  - 가능합니다. `scripts/bootstrap.ps1 -Task demo`가 샘플 DB/CSV를 생성해 네트워크 없이도 대시보드를 띄웁니다.

- 레이아웃이 바뀌면 어떻게 하나요?
  - `docs/check/DOM_REPORT.md`와 `docs/check/version_selectors.yaml` 기준으로 파서를 보정합니다. 스모크 테스트로 회귀를 방지합니다.

