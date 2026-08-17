# Troubleshooting (로컬/운영)

## 공통
- Chrome/Driver 오류: Chrome 업데이트, `pip install --upgrade selenium`, 재부팅
- 네트워크/차단 의심: 요청 간격 늘리기, 재개 사용, Selenium 모드 전환(headful)
- 인코딩 깨짐: docs는 UTF-8(무BOM) 권장. Windows 메모장 대신 VS Code 사용

## project2 (출전 랭킹)
- 무자료: 페이지에 “검색 결과가 없습니다” → 실패로 간주하지 않음. `project2/state/nodata_YYYY-MM-DD.txt` 생성
- 파싱 실패: `project2/state/raw_html/YYYY-MM-DD.html` 스냅샷 확인 → `project2/app/parser/selectors.py` 보강 필요 여부 판단
- 실패일 재시도: PowerShell에서 `Get-ChildItem project2/state -Filter 'failures_*.txt' | % { $d = ($_.BaseName -replace '^failures_',''); python -m project2.app.cli run --from $d --to $d --fast }`

## BestPrice (project)
- HTML 레이아웃 변경: `docs/check/DOM_REPORT.md`와 연도별 체크 HTML 참고
- 이미지 누락: `app/services/images.py`의 not_found.png 경로 확인, backfill 스크립트 사용
